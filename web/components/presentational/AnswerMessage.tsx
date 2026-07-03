import type { ChatResponse } from "@/types/chat";

interface AnswerMessageProps {
  response: ChatResponse;
}

export function AnswerMessage({ response }: AnswerMessageProps) {
  return (
    <section className="answer-message" aria-label="回答">
      <p>{response.answer}</p>
    </section>
  );
}
