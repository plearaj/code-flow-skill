import { Component, Input } from "@angular/core";

@Component({
  selector: "app-summary",
  template: `<span>{{ total }}</span>`,
})
export class SummaryComponent {
  @Input() total = 0;
}
