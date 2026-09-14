import { Badge } from "@/components/ui";
import {
  STATUS_LABELS,
  STAGE_LABELS,
  STATUS_BADGE_COLORS,
  STAGE_BADGE_COLORS,
} from "@/constants";
import type { ApiStatus, ApiStage } from "@/types";

interface StatusBadgeProps {
  status: ApiStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <Badge className={STATUS_BADGE_COLORS[status]}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}

interface StageBadgeProps {
  stage: ApiStage;
}

export function StageBadge({ stage }: StageBadgeProps) {
  return (
    <Badge className={STAGE_BADGE_COLORS[stage]}>
      {STAGE_LABELS[stage]}
    </Badge>
  );
}