"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, Eye } from "lucide-react";

interface QuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
}

interface QuizDisplayProps {
  questions: QuizQuestion[];
}

export function QuizDisplay({ questions }: QuizDisplayProps) {
  const [selectedAnswers, setSelectedAnswers] = useState<
    Record<number, number>
  >({});
  const [revealedAnswers, setRevealedAnswers] = useState<Set<number>>(
    new Set()
  );

  function selectAnswer(questionIdx: number, optionIdx: number) {
    if (revealedAnswers.has(questionIdx)) return;
    setSelectedAnswers((prev) => ({ ...prev, [questionIdx]: optionIdx }));
  }

  function revealAnswer(questionIdx: number) {
    setRevealedAnswers((prev) => new Set([...prev, questionIdx]));
  }

  const answeredCount = Object.keys(selectedAnswers).length;
  const correctCount = Object.entries(selectedAnswers).filter(
    ([qIdx, aIdx]) =>
      revealedAnswers.has(Number(qIdx)) &&
      aIdx === questions[Number(qIdx)].correct_index
  ).length;

  return (
    <div className="space-y-6">
      {revealedAnswers.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 p-4">
          <span className="text-sm font-medium">Score:</span>
          <Badge variant={correctCount === revealedAnswers.size ? "default" : "secondary"}>
            {correctCount} / {revealedAnswers.size} correct
          </Badge>
        </div>
      )}

      {questions.map((q, qIdx) => {
        const isRevealed = revealedAnswers.has(qIdx);
        const selected = selectedAnswers[qIdx];
        const isCorrect = selected === q.correct_index;

        return (
          <Card key={qIdx}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium">
                <span className="text-muted-foreground mr-2">
                  Q{qIdx + 1}.
                </span>
                {q.question}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                {q.options.map((option, oIdx) => {
                  let optionClass =
                    "border rounded-lg p-3 text-sm cursor-pointer transition-all";

                  if (isRevealed) {
                    if (oIdx === q.correct_index) {
                      optionClass +=
                        " border-green-500 bg-green-50 text-green-800";
                    } else if (oIdx === selected && !isCorrect) {
                      optionClass +=
                        " border-red-500 bg-red-50 text-red-800";
                    } else {
                      optionClass += " border-border text-muted-foreground";
                    }
                  } else if (oIdx === selected) {
                    optionClass +=
                      " border-primary bg-primary/5 text-primary";
                  } else {
                    optionClass +=
                      " border-border hover:border-primary/50 hover:bg-muted/50";
                  }

                  return (
                    <button
                      key={oIdx}
                      onClick={() => selectAnswer(qIdx, oIdx)}
                      disabled={isRevealed}
                      className={`w-full text-left ${optionClass}`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium">
                          {String.fromCharCode(65 + oIdx)}
                        </span>
                        <span>{option}</span>
                        {isRevealed && oIdx === q.correct_index && (
                          <CheckCircle2 className="ml-auto h-5 w-5 text-green-600" />
                        )}
                        {isRevealed &&
                          oIdx === selected &&
                          !isCorrect && (
                            <XCircle className="ml-auto h-5 w-5 text-red-600" />
                          )}
                      </div>
                    </button>
                  );
                })}
              </div>

              {!isRevealed && selected !== undefined && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => revealAnswer(qIdx)}
                >
                  <Eye className="mr-1.5 h-4 w-4" />
                  Reveal Answer
                </Button>
              )}

              {isRevealed && (
                <div className="rounded-lg bg-muted p-3 text-sm">
                  <p className="font-medium mb-1">
                    {isCorrect ? "Correct!" : "Incorrect"}
                  </p>
                  <p className="text-muted-foreground">{q.explanation}</p>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
