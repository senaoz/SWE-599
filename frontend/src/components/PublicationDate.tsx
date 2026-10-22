import { Badge } from "@/components/base/badges/badges";

const RECENT_DAYS = 7;
const DAY_MS = 24 * 60 * 60 * 1000;

// "YYYY-MM-DD" as a local calendar date, so the day doesn't shift with the time zone.
function parseDay(value: string): Date | null {
  const [y, m, d] = value.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function daysFromToday(value: string): number | null {
  const day = parseDay(value);
  if (!day) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((day.getTime() - today.getTime()) / DAY_MS);
}

/** The publication date, with a badge for papers from the last week or dated after today. */
export default function PublicationDate({ date }: { date: string | null }) {
  if (!date) return null;
  const days = daysFromToday(date);

  return (
    <>
      <span className="text-xs text-tertiary">{date}</span>
      {days !== null && days > 0 && (
        <span title="OpenAlex lists a publication date after today: often a journal's scheduled issue date, sometimes a date entered by the uploader.">
          <Badge type="color" color="purple" size="sm">
            Future date
          </Badge>
        </span>
      )}
      {days !== null && days <= 0 && days > -RECENT_DAYS && (
        <span title={`Published in the last ${RECENT_DAYS} days`}>
          <Badge type="color" color="success" size="sm">
            This week
          </Badge>
        </span>
      )}
    </>
  );
}
