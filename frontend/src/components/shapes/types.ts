import type { QueryResponse } from "../../api/types";

export interface ShapeProps {
  res: QueryResponse;
  lines: string[];
  // True when the SQL result is unusable or absent: charts must not render.
  suppressCharts: boolean;
  onCiteClick: (n: number) => void;
}
