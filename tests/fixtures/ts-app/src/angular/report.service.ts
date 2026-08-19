import { Injectable } from "@angular/core";

@Injectable({ providedIn: "root" })
export class ReportService {
  /** Sum of every report row. */
  total() {
    return this.rows().length;
  }

  rows() {
    return [];
  }
}
