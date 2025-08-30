import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterator, List, Literal
from .llm_provider import Message
from pydantic import BaseModel, Field


class JudgeResponse(BaseModel):
    reasoning: str = Field(
        ...,
        description="A very detailed reasoning for the verdict, pointing out where exactly did the model fail, and why should you consider this a failure.",
    )
    verdict: Literal["YES", "NO"]





@dataclass
class Question:
    """Represents a single benchmark question."""

    question_id: str
    axis: str
    conversation: List[Message]
    target_question: str
    pass_criteria: str

    @classmethod
    def from_dict(cls, data: Dict) -> "Question":
        """Create a Question instance from a dictionary."""
        conversation = [
            Message(turn["role"], turn["content"])
            for turn in data.get("CONVERSATION", [])
        ]

        return cls(
            question_id=data.get("QUESTION_ID", ""),
            axis=data.get("AXIS", "UNKNOWN"),
            conversation=conversation,
            target_question=data.get("TARGET_QUESTION", ""),
            pass_criteria=data.get("PASS_CRITERIA", ""),
        )

    def to_dict(self) -> Dict:
        """Convert Question instance back to dictionary format."""
        return {
            "QUESTION_ID": self.question_id,
            "AXIS": self.axis,
            "CONVERSATION": [
                {"role": turn.role, "content": turn.content}
                for turn in self.conversation
            ],
            "TARGET_QUESTION": self.target_question,
            "PASS_CRITERIA": self.pass_criteria,
        }

    def get_user_messages(self) -> List[str]:
        """Get all user messages from the conversation."""
        return [turn.content for turn in self.conversation if turn.role == "user"]

    def get_assistant_messages(self) -> List[str]:
        """Get all assistant messages from the conversation."""
        return [turn.content for turn in self.conversation if turn.role == "assistant"]

    def get_conversation_length(self) -> int:
        """Get the total number of conversation turns."""
        return len(self.conversation)

    def __str__(self) -> str:
        return f"[{self.axis}] {self.target_question[:100]}..."


class QuestionCollection:
    """A collection of benchmark questions with various querying capabilities."""

    def __init__(self, questions: List[Question]):
        """
        Initialize the collection with a list of questions.

        Args:
            questions: List of Question objects
        """
        self.questions = questions
        self._organize_by_axis()

    def _organize_by_axis(self):
        """Organize questions by their AXIS for efficient querying."""
        self.questions_by_axis = defaultdict(list)
        for question in self.questions:
            self.questions_by_axis[question.axis].append(question)

    def __len__(self) -> int:
        """Return the total number of questions."""
        return len(self.questions)

    def __iter__(self) -> Iterator[Question]:
        """Iterate through all questions."""
        for question in self.questions:
            yield question

    def __getitem__(self, index: int) -> Question:
        """Get a question by index."""
        return self.questions[index]

    def get_by_axis(self, axis: str) -> List[Question]:
        """
        Get all questions for a specific AXIS.

        Args:
            axis: The AXIS to filter by

        Returns:
            List of questions for the specified AXIS
        """
        return self.questions_by_axis.get(axis, [])

    def get_available_axes(self) -> List[str]:
        """Get list of all available AXIS values."""
        return list(self.questions_by_axis.keys())

    def get_axis_counts(self) -> Dict[str, int]:
        """Get count of questions for each AXIS."""
        return {
            axis: len(questions) for axis, questions in self.questions_by_axis.items()
        }

    def filter_by_criteria(self, **kwargs) -> List[Question]:
        """
        Filter questions by various criteria.

        Args:
            **kwargs: Filter criteria (e.g., axis="INFERENCE_MEMORY")

        Returns:
            List of questions matching the criteria
        """
        filtered = self.questions

        if "axis" in kwargs:
            filtered = [q for q in filtered if q.axis == kwargs["axis"]]

        if "min_conversation_length" in kwargs:
            filtered = [
                q
                for q in filtered
                if q.get_conversation_length() >= kwargs["min_conversation_length"]
            ]

        if "max_conversation_length" in kwargs:
            filtered = [
                q
                for q in filtered
                if q.get_conversation_length() <= kwargs["max_conversation_length"]
            ]

        if "contains_text" in kwargs:
            text = kwargs["contains_text"].lower()
            filtered = [q for q in filtered if text in q.target_question.lower()]

        return filtered

    def get_random_sample(self, size: int = 10) -> List[Question]:
        """
        Get a random sample of questions.

        Args:
            size: Number of questions to sample

        Returns:
            List of randomly sampled questions
        """
        import random

        return random.sample(self.questions, min(size, len(self.questions)))

    def get_statistics(self) -> Dict:
        """Get comprehensive statistics about the question collection."""
        stats = {
            "total_questions": len(self.questions),
            "axes": self.get_axis_counts(),
            "conversation_lengths": {},
            "avg_conversation_length": 0,
        }

        # Calculate conversation length statistics
        lengths = [q.get_conversation_length() for q in self.questions]
        if lengths:
            stats["conversation_lengths"] = {
                "min": min(lengths),
                "max": max(lengths),
                "avg": sum(lengths) / len(lengths),
            }
            stats["avg_conversation_length"] = stats["conversation_lengths"]["avg"]

        return stats


class BenchmarkDataLoader:
    """
    A dataloader for benchmark questions that returns Question objects.
    """

    def __init__(self, file_path: str):
        """
        Initialize the dataloader with a JSONL file path.

        Args:
            file_path: Path to the JSONL file containing benchmark questions
        """
        self.file_path = file_path
        self.question_collection = None
        self._load_data()

    def _load_data(self):
        """Load all questions from the JSONL file and create Question objects."""
        questions = []

        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        question_data = json.loads(line)
                        question = Question.from_dict(question_data)
                        questions.append(question)

                    except json.JSONDecodeError as e:
                        print(f"Warning: Could not parse line {line_num}: {e}")
                        continue

        except FileNotFoundError:
            raise FileNotFoundError(f"Benchmark file not found: {self.file_path}")
        except Exception as e:
            raise Exception(f"Error loading benchmark file: {e}")

        self.question_collection = QuestionCollection(questions)

    def get_questions(self) -> QuestionCollection:
        """Get the question collection."""

        assert self.question_collection is not None, "Data not loaded yet"
        return self.question_collection

    def __len__(self) -> int:
        """Return the total number of questions."""
        return len(self.question_collection) if self.question_collection else 0

    def __iter__(self) -> Iterator[Question]:
        """Iterate through all questions."""
        if self.question_collection:
            for question in self.question_collection:
                yield question

    def get_questions_by_axis(self, axis: str) -> List[Question]:
        """Get questions for a specific AXIS."""
        return (
            self.question_collection.get_by_axis(axis)
            if self.question_collection
            else []
        )

    def get_available_axes(self) -> List[str]:
        """Get list of all available AXIS values."""
        return (
            self.question_collection.get_available_axes()
            if self.question_collection
            else []
        )

    def get_axis_counts(self) -> Dict[str, int]:
        """Get count of questions for each AXIS."""
        return (
            self.question_collection.get_axis_counts()
            if self.question_collection
            else {}
        )


# Example usage
if __name__ == "__main__":
    # Initialize the dataloader
    loader = BenchmarkDataLoader("benchmark_questions.jsonl")

    # Get the question collection
    questions = loader.get_questions()

    print(f"✓ Loaded {len(questions)} total questions")
    print(f"✓ Available axes: {', '.join(questions.get_available_axes())}")
    print(f"✓ Questions per axis: {questions.get_axis_counts()}")
    print()

    # Example: Work with individual Question objects
    print("=== Example: Working with Question objects ===")
    first_question = questions[0]
    print(f"First question: {first_question}")
    print(f"Conversation length: {first_question.get_conversation_length()}")
    print(f"User messages: {len(first_question.get_user_messages())}")
    print(f"Assistant messages: {len(first_question.get_assistant_messages())}")
    print()

    # Example: Filter questions
    print("=== Example: Filtering questions ===")
    long_conversations = questions.filter_by_criteria(min_conversation_length=5)
    print(f"Questions with 5+ conversation turns: {len(long_conversations)}")

    restaurant_questions = questions.filter_by_criteria(contains_text="restaurant")
    print(f"Questions containing 'restaurant': {len(restaurant_questions)}")

    # Example: Get statistics
    print("\n=== Example: Statistics ===")
    stats = questions.get_statistics()
    print(f"Average conversation length: {stats['avg_conversation_length']:.1f}")
    print(
        f"Conversation length range: {stats['conversation_lengths']['min']} - {stats['conversation_lengths']['max']}"
    )
