import en_core_web_sm
import json
import numpy as np
import random
import re
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration, BertTokenizer, BertForSequenceClassification
from typing import Any, List, Mapping, Tuple

class QuestionGenerator:
    """A transformer-based NLP system for generating reading comprehension-style questions from texts.
    It can generate full sentence questions, multiple choice questions, or a mix of the two styles.

    To filter out low-quality questions, questions are assigned a score and ranked once they have
    been generated. Only the top k questions will be returned. This behavior can be turned off
    by setting use_evaluator=False.
    """

    def __init__(self) -> None:
        QG_PRETRAINED = "t5-large"
        self.ANSWER_TOKEN = "<answer>"
        self.CONTEXT_TOKEN = "<context>"
        self.SEQ_LENGTH = 512

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.qg_tokenizer = T5Tokenizer.from_pretrained(QG_PRETRAINED, use_fast=False)
        self.qg_model = T5ForConditionalGeneration.from_pretrained(QG_PRETRAINED)
        self.qg_model.to(self.device)
        self.qg_model.eval()

        self.qa_evaluator = QAEvaluator()

    def generate(
        self,
        article: str,
        use_evaluator: bool = True,
        num_questions: int = 10,
        answer_style: str = "all"
    ) -> List:
        """Takes an article and generates a set of question and answer pairs. If use_evaluator
        is True, then QA pairs will be ranked and filtered based on their quality. answer_style
        should be selected from ["all", "sentences", "multiple_choice"].
        """
        print("Generating questions...\n")

        qg_inputs, qg_answers = self.generate_qg_inputs(article, answer_style)
        generated_questions = self.generate_questions_from_inputs(qg_inputs)

        message = "{} questions don't match {} answers".format(
            len(generated_questions), len(qg_answers)
        )
        assert len(generated_questions) == len(qg_answers), message

        if use_evaluator:
            print("Evaluating QA pairs...\n")
            encoded_qa_pairs = self.qa_evaluator.encode_qa_pairs(
                generated_questions, qg_answers
            )
            scores = self.qa_evaluator.get_scores(encoded_qa_pairs)

            qa_list = self._get_ranked_qa_pairs(
                generated_questions, qg_answers, scores, num_questions
            )
        else:
            print("Skipping evaluation step.\n")
            qa_list = self._get_all_qa_pairs(generated_questions, qg_answers)

        return qa_list

    def generate_qg_inputs(self, text: str, answer_style: str) -> Tuple[List[str], List[str]]:
        """Given a text, returns a list of model inputs and a list of corresponding answers.
        Model inputs take the form "answer_token <answer text> context_token <context text>" where
        the answer is a string extracted from the text, and the context is the wider text surrounding
        the context.
        """

        VALID_ANSWER_STYLES = ["all", "sentences", "multiple_choice"]

        if answer_style not in VALID_ANSWER_STYLES:
            raise ValueError(
                "Invalid answer style {}. Please choose from {}".format(
                    answer_style, VALID_ANSWER_STYLES
                )
            )

        inputs = []
        answers = []

        if answer_style in ["sentences", "all"]:
            segments = self._split_into_segments(text)

            for segment in segments:
                sentences = self._split_text(segment)
                prepped_inputs, prepped_answers = self._prepare_qg_inputs(
                    sentences, segment
                )
                inputs.extend(prepped_inputs)
                answers.extend(prepped_answers)

        if answer_style in ["multiple_choice", "all"]:
            sentences = self._split_text(text)
            prepped_inputs, prepped_answers = self._prepare_qg_inputs_MC(sentences)
            inputs.extend(prepped_inputs)
            answers.extend(prepped_answers)

        return inputs, answers

    def generate_questions_from_inputs(self, qg_inputs: List) -> List[str]:
        """Given a list of concatenated answers and contexts, with the form:
        "answer_token <answer text> context_token <context text>", generates a list of 
        questions.
        """
        generated_questions = []

        for qg_input in qg_inputs:
            question = self._generate_question(qg_input)
            generated_questions.append(question)

        return generated_questions

    def _split_text(self, text: str) -> List[str]:
        """Splits the text into sentences, and attempts to split or truncate long sentences."""
        MAX_SENTENCE_LEN = 128
        # sentences = re.findall(".*?[.!\?]", text)
        sentences = re.findall(r'[^.!?]*[.!?]', text)
        cut_sentences = []

        for sentence in sentences:
            if len(sentence) > MAX_SENTENCE_LEN:
                cut_sentences.extend(re.split("[,;:)]", sentence))

        cut_sentences = [s for s in sentences if len(s.split(" ")) > 5]
        sentences = sentences + cut_sentences

        return list(set([s.strip() for s in sentences]))

    def _split_into_segments(self, text: str) -> List[str]:
        """Splits a long text into segments short enough to be input into the transformer network.
        Segments are used as context for question generation.
        """
        MAX_TOKENS = 490
        paragraphs = text.split("\n")
        tokenized_paragraphs = [
            self.qg_tokenizer(p)["input_ids"] for p in paragraphs if len(p) > 0
        ]
        segments = []

        while len(tokenized_paragraphs) > 0:
            segment = []

            while len(segment) < MAX_TOKENS and len(tokenized_paragraphs) > 0:
                paragraph = tokenized_paragraphs.pop(0)
                segment.extend(paragraph)
            segments.append(segment)

        return [self.qg_tokenizer.decode(s, skip_special_tokens=True) for s in segments]

    def _prepare_qg_inputs(
        self,
        sentences: List[str],
        text: str
    ) -> Tuple[List[str], List[str]]:
        """Uses sentences as answers and the text as context. Returns a tuple of (model inputs, answers).
        Model inputs are "answer_token <answer text> context_token <context text>" 
        """
        inputs = []
        answers = []

        for sentence in sentences:
            qg_input = f"{self.ANSWER_TOKEN} {sentence} {self.CONTEXT_TOKEN} {text}"
            inputs.append(qg_input)
            answers.append(sentence)

        return inputs, answers

    def _prepare_qg_inputs_MC(self, sentences: List[str]) -> Tuple[List[str], List[str]]:
        """Performs NER on the text, and uses extracted entities as candidate answers for multiple-choice
        questions. Sentences are used as context, and entities as answers. Returns a tuple of (model inputs, answers). 
        Model inputs are "answer_token <answer text> context_token <context text>"
        """
        spacy_nlp = en_core_web_sm.load()
        docs = list(spacy_nlp.pipe(sentences, disable=["parser"]))
        inputs_from_text = []
        answers_from_text = []

        for doc, sentence in zip(docs, sentences):
            entities = doc.ents
            if entities:
                for entity in entities:
                    qg_input = f"{self.ANSWER_TOKEN} {entity.text} {self.CONTEXT_TOKEN} {sentence}"
                    answers = self._get_MC_answers(entity, docs)
                    inputs_from_text.append(qg_input)
                    answers_from_text.append(answers)

        return inputs_from_text, answers_from_text

    def _get_MC_answers(self, correct_answer: Any, docs: Any) -> List[Mapping[str, Any]]:
        """Finds a set of alternative answers for a multiple-choice question. Will attempt to find
        alternatives of the same entity type as correct_answer if possible.
        """
        entities = []

        for doc in docs:
            entities.extend([{"text": e.text, "label_": e.label_} for e in doc.ents])

        entities_json = [json.dumps(kv) for kv in entities]
        pool = set(entities_json)
        num_choices = min(4, len(pool)) - 1

        final_choices = []
        correct_label = correct_answer.label_
        final_choices.append({"answer": correct_answer.text, "correct": True})
        pool.remove(json.dumps({"text": correct_answer.text, "label_": correct_answer.label_}))

        matches = [e for e in pool if correct_label in e]

        if len(matches) < num_choices:
            choices = matches
            pool = pool.difference(set(choices))
            choices.extend(random.sample(list(pool), num_choices - len(choices)))
        else:
            choices = random.sample(matches, num_choices)

        choices = [json.loads(s) for s in choices]

        for choice in choices:
            final_choices.append({"answer": choice["text"], "correct": False})

        random.shuffle(final_choices)
        return final_choices

    @torch.no_grad()
    def _generate_question(self, qg_input: str) -> str:
        """Takes qg_input which is the concatenated answer and context, and uses it to generate
        a question sentence. The generated question is decoded and then returned.
        """
        encoded_input = self._encode_qg_input(qg_input)
        encoded_input = encoded_input.to(self.device)
        encoded_output = self.qg_model.generate(
            input_ids=encoded_input["input_ids"],
            attention_mask=encoded_input["attention_mask"],
            max_length=64,
        )

        question = self.qg_tokenizer.decode(
            encoded_output[0],
            skip_special_tokens=True
        )

        return question

    def _encode_qg_input(self, qg_input: str) -> Any:
        """Encodes qg_input into tokens IDs that can be input into a transformer model."""
        return self.qg_tokenizer(
            qg_input,
            truncation=True,
            padding="max_length",
            max_length=self.SEQ_LENGTH,
            return_tensors="pt"
        )

    def _get_ranked_qa_pairs(
        self, questions: List[str], answers: List[str], scores: Any, num_questions: int
    ) -> List[Mapping[str, Any]]:
        """Ranks and returns the top k question/answer pairs."""
        qa_list = []

        for i, s in enumerate(scores):
            qa = {"question": questions[i], "answer": answers[i], "score": s}
            qa_list.append(qa)

        qa_list = sorted(qa_list, key=lambda x: x["score"], reverse=True)
        qa_list = qa_list[:num_questions]

        return qa_list

    def _get_all_qa_pairs(
        self, questions: List[str], answers: List[str]
    ) -> List[Mapping[str, Any]]:
        """Returns all question answer pairs."""
        return [{"question": q, "answer": a} for q, a in zip(questions, answers)]


class QAEvaluator:
    """A BERT-based QA model for evaluating the quality of question-answer pairs.
    Higher scores indicate better question-answer quality.
    """

    def __init__(self):
        QAE_PRETRAINED = "bert-large-cased"
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.qa_evaluator_tokenizer = BertTokenizer.from_pretrained(QAE_PRETRAINED)
        self.qa_evaluator = BertForSequenceClassification.from_pretrained(
            QAE_PRETRAINED, num_labels=1
        )
        self.qa_evaluator.to(self.device)
        self.qa_evaluator.eval()

    @torch.no_grad()
    def encode_qa_pairs(self, questions: List[str], answers: List[str]) -> Any:
        """Encodes QA pairs for evaluation using a BERT model."""
        encoded_qa_pairs = self.qa_evaluator_tokenizer(
            questions,
            answers,
            truncation=True,
            padding="max_length",
            max_length=512,
            return_tensors="pt"
        )

        return encoded_qa_pairs

    @torch.no_grad()
    def get_scores(self, encoded_qa_pairs: Any) -> Any:
        """Given a list of encoded QA pairs, returns scores for them."""
        encoded_qa_pairs = encoded_qa_pairs.to(self.device)
        outputs = self.qa_evaluator(**encoded_qa_pairs)

        return outputs[0].squeeze(-1).tolist()
