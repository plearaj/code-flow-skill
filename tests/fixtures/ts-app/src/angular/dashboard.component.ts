import { Component, Input, OnInit } from "@angular/core";
import { ReportService } from "./report.service";

@Component({
  selector: "app-dashboard",
  template: `<app-summary [total]="total"></app-summary>`,
})
export class DashboardComponent implements OnInit {
  @Input() title: string;
  total = 0;

  constructor(private reports: ReportService) {}

  /** Load the dashboard totals. */
  ngOnInit() {
    this.total = this.reports.total();
  }
}
