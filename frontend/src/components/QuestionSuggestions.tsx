export default function QuestionSuggestions({ questions, onSelect }: {
  questions?: string[];
  onSelect?: (question: string) => void;
}) {
  if (!questions?.length || !onSelect) return null;
  return <div className="question-suggestions" role="group" aria-label="Suggested questions">
    {questions.slice(0, 3).map(question =>
      <button type="button" key={question} onClick={() => onSelect(question)}>{question}</button>
    )}
  </div>;
}
