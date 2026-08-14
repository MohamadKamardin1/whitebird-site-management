/* White Bird Zanzibar — small admin behaviour helpers.
   Keeps inline JS out of templates. */
(function () {
  "use strict";

  function badgeify(selector) {
    document.querySelectorAll(selector).forEach(function (el) {
      var text = (el.textContent || "").trim().toLowerCase();
      if (!text) return;
      var cls = "wb-badge";
      if (/(passed|completed|verified|closed|active|submitted|success)/.test(text)) {
        cls += " wb-badge-passed";
      } else if (/(failed|urgent|damaged|lost)/.test(text)) {
        cls += " wb-badge-failed";
      } else if (/(needs.?attention|in.?progress|high|returned|reopened|reviewed)/.test(text)) {
        cls += " wb-badge-needs_attention";
      } else if (/(open|draft|low|medium|pending)/.test(text)) {
        cls += " wb-badge-open";
      }
      el.classList.add(cls);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    badgeify(".field-status, .field-priority, .field-overall_status, .field-review_status");
  });
})();
