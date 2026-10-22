import { ThumbsDown, ThumbsUp } from "@untitledui/icons";
import { cx } from "@/utils/cx";

interface FeedbackButtonsProps {
  value: boolean | null;
  onChange: (isRelevant: boolean) => void;
  size?: "sm" | "md";
}

/** Thumbs up/down for one researcher under one paper. Clicks don't reach the card underneath. */
export default function FeedbackButtons({ value, onChange, size = "sm" }: FeedbackButtonsProps) {
  const icon = size === "sm" ? "size-3.5" : "size-4";
  const base = "cursor-pointer rounded-md p-1 transition-colors outline-focus-ring focus-visible:outline-2";
  return (
    <span className="inline-flex items-center gap-0.5">
      <button
        type="button"
        aria-label="Relevant"
        aria-pressed={value === true}
        title="Relevant"
        onClick={(e) => {
          e.stopPropagation();
          onChange(true);
        }}
        className={cx(base, value === true ? "bg-success-primary text-fg-success-primary" : "text-fg-quaternary hover:text-fg-success-primary")}
      >
        <ThumbsUp className={icon} />
      </button>
      <button
        type="button"
        aria-label="Not relevant"
        aria-pressed={value === false}
        title="Not relevant"
        onClick={(e) => {
          e.stopPropagation();
          onChange(false);
        }}
        className={cx(base, value === false ? "bg-error-primary text-fg-error-primary" : "text-fg-quaternary hover:text-fg-error-primary")}
      >
        <ThumbsDown className={icon} />
      </button>
    </span>
  );
}
