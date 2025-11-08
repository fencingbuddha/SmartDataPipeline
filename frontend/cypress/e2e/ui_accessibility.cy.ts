/// <reference types="cypress" />

type RGB = { r: number; g: number; b: number; a: number };

const MIN_CONTRAST = 4.5;
const AUTH_PREFIX =
  (Cypress.env("VITE_AUTH_STORAGE_PREFIX") as string) || "sdp_";

const FOCUSABLE_SELECTORS = [
  'a[href]',
  "button",
  "input:not([type='hidden'])",
  "select",
  "textarea",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

const NAMED_COLORS: Record<string, RGB> = {
  black: { r: 0, g: 0, b: 0, a: 1 },
  white: { r: 255, g: 255, b: 255, a: 1 },
  red:   { r: 255, g: 0, b: 0, a: 1 },
  green: { r: 0, g: 128, b: 0, a: 1 },
  blue:  { r: 0, g: 0, b: 255, a: 1 },
  transparent: { r: 0, g: 0, b: 0, a: 0 },
};

const parseColor = (value: string | null): RGB | null => {
  if (!value) return null;
  const v = value.trim().toLowerCase();

  // named colors
  if (v in NAMED_COLORS) return NAMED_COLORS[v];

  // hex (#rgb, #rgba, #rrggbb, #rrggbbaa) — treat alpha if present
  if (v.startsWith("#")) {
    const hex = v.slice(1);
    const expand = (h: string) => (h.length === 1 ? h + h : h);
    if (hex.length === 3 || hex.length === 4) {
      const r = parseInt(expand(hex[0]), 16);
      const g = parseInt(expand(hex[1]), 16);
      const b = parseInt(expand(hex[2]), 16);
      const a = hex.length === 4 ? parseInt(expand(hex[3]), 16) / 255 : 1;
      return { r, g, b, a };
    }
    if (hex.length === 6 || hex.length === 8) {
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      const a = hex.length === 8 ? parseInt(hex.slice(6, 8), 16) / 255 : 1;
      return { r, g, b, a };
    }
    return null;
  }

  // rgb/rgba()
  const match = v.match(/rgba?\(([^)]+)\)/i);
  if (!match) return null;
  const parts = match[1].split(",").map((p) => p.trim());
  const r = Number(parts[0]);
  const g = Number(parts[1]);
  const b = Number(parts[2]);
  const a = parts[3] !== undefined ? Number(parts[3]) : 1;
  return { r, g, b, a };
};

const toLuminance = ({ r, g, b }: RGB): number => {
  const channel = (c: number) => {
    const normalized = c / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : Math.pow((normalized + 0.055) / 1.055, 2.4);
  };
  return (
    0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
  );
};

const contrastRatio = (fg: RGB, bg: RGB): number => {
  const L1 = toLuminance(fg) + 0.05;
  const L2 = toLuminance(bg) + 0.05;
  return Math.max(L1, L2) / Math.min(L1, L2);
};

const nearestOpaqueBackground = (el: HTMLElement, win: Window): RGB => {
  let current: HTMLElement | null = el;
  while (current) {
    const bg = parseColor(win.getComputedStyle(current).backgroundColor);
    if (bg && bg.a !== 0) return bg;
    current = current.parentElement;
  }
  return (
    parseColor(win.getComputedStyle(win.document.body).backgroundColor) ?? {
      r: 0,
      g: 0,
      b: 0,
      a: 1,
    }
  );
};

const isElementVisible = (el: HTMLElement, win: Window) => {
  const style = win.getComputedStyle(el);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.opacity === "0"
  ) {
    return false;
  }
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
};

const tabbableElements = (doc: Document): HTMLElement[] => {
  const win = doc.defaultView!;
  const nodes = Array.from(
    doc.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS),
  );
  return nodes.filter((el) => {
    if (el.hasAttribute("disabled")) return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    if (!isElementVisible(el, win)) {
      return false;
    }
    return el.tabIndex >= 0;
  });
};

const describeActionable = (el: HTMLElement) => {
  const dataId = el.getAttribute("data-testid");
  if (dataId) return dataId;
  if (el.matches("input[type='email']")) return "email input";
  if (el.matches("input[type='password']")) return "password input";
  const aria = el.getAttribute("aria-label");
  if (aria) return aria;
  const text = el.textContent?.trim();
  if (text) return text;
  return el.tagName.toLowerCase();
};

const visitLoginScreen = () => {
  cy.visit("/");
  cy.window().then((win) => {
    win.localStorage.removeItem(`${AUTH_PREFIX}access`);
    win.localStorage.removeItem(`${AUTH_PREFIX}refresh`);
  });
  cy.reload();
  cy.findByTestId("login-title", { timeout: 10000 }).should("be.visible");
};

const stubDashboardApis = () => {
  cy.intercept("GET", "**/api/sources", {
    statusCode: 200,
    body: [{ id: 1, name: "demo-source" }],
  }).as("sources");

  cy.intercept("GET", "**/api/metrics/names*", {
    statusCode: 200,
    body: ["events_total", "orders_total"],
  }).as("metricNames");

  cy.intercept("GET", "**/api/metrics/daily*", {
    statusCode: 200,
    body: [
      {
        metric_date: "2025-01-01",
        value_sum: 42,
        value_avg: 6,
        value_count: 3,
        value_distinct: 2,
      },
      {
        metric_date: "2025-01-02",
        value_sum: 48,
        value_avg: 7,
        value_count: 2,
        value_distinct: 1,
      },
    ],
  }).as("daily");

  cy.intercept("GET", "**/api/metrics/anomaly/rolling*", {
    statusCode: 200,
    body: [],
  });

  cy.intercept("GET", "**/api/forecast/daily*", {
    statusCode: 200,
    body: [],
  });

  cy.intercept("GET", "**/api/forecast/reliability*", {
    statusCode: 200,
    body: {
      score: 88,
      grade: "A",
      summary: { mae: 0.12, rmse: 0.42 },
    },
  }).as("reliability");
};

const visitDashboard = () => {
  stubDashboardApis();
  cy.visit("/");
  cy.wait(["@sources", "@metricNames", "@daily", "@reliability"]);
  cy.get("[data-testid='rel-badge']", { timeout: 10000 }).should("be.visible");
};

const ensureFocusIndicators = (selectors: string[]) => {
  selectors.forEach((selector) => {
    cy.get(selector)
      .should("be.visible")
      .focus()
      .then(($el) => {
        const element = $el[0] as HTMLElement;
        const win = element.ownerDocument.defaultView!;
        const style = win.getComputedStyle(element);
        const outlineWidth = parseFloat(style.outlineWidth || "0");
        const outlineVisible = style.outlineStyle !== "none" && outlineWidth > 0;
        const shadowVisible = style.boxShadow !== "none" && style.boxShadow !== "";
        const borderWidth = parseFloat(style.borderWidth || "0");
        const borderVisible = style.borderStyle !== "none" && borderWidth > 0;
        const label =
          element.getAttribute("data-testid") ||
          element.getAttribute("aria-label") ||
          element.getAttribute("type") ||
          element.textContent?.trim() ||
          selector;
        expect(
          outlineVisible || shadowVisible || borderVisible,
          `Focus indicator missing for ${label}`,
        ).to.be.true;
      })
      .blur();
  });
};

const assertContrast = (selector: string) => {
  cy.get(selector)
    .should("be.visible")
    .each(($el) => {
      const element = $el[0] as HTMLElement;
      const win = element.ownerDocument.defaultView!;
      const fg = parseColor(win.getComputedStyle(element).color);
      const bg = nearestOpaqueBackground(element, win);
      expect(fg, `Color missing for ${selector}`).to.not.be.null;
      const ratio = contrastRatio(fg!, bg);
      expect(
        ratio,
        `${selector} contrast ${ratio.toFixed(2)} should be >= ${MIN_CONTRAST}`,
      ).to.be.gte(MIN_CONTRAST);
    });
};

describe("UI accessibility audit", () => {
  it("keeps login form copy above the 4.5:1 contrast ratio", () => {
    visitLoginScreen();
    assertContrast("[data-testid='login-title']");
    assertContrast("form label");
    assertContrast("form button");
  });

  it("ensures tab traversal hits every actionable dashboard control", () => {
    visitDashboard();
    const actionableOrder = [
      "filter-source",
      "filter-metric",
      "filter-start",
      "filter-end",
      "btn-run",
      "btn-reset",
      "btn-signout",
      "quick-range",
      "anoms-window",
      "anoms-z",
      "toggle-anoms",
      "toggle-forecast",
      "rel-badge",
      "btn-export-png",
      "btn-export-csv",
    ];
    const expectedSet = new Set(actionableOrder);
    cy.document().then((doc) => {
      const focusables = tabbableElements(doc).filter((el) =>
        expectedSet.has(el.getAttribute("data-testid") || ""),
      );
      const actualOrder = focusables.map((el) =>
        el.getAttribute("data-testid")!,
      );
      const isSubsequence = (needle: string[], haystack: string[]) => {
        let i = 0;
        for (const h of haystack) {
          if (i < needle.length && h === needle[i]) i++;
        }
        return i === needle.length;
      };
      expect(
        isSubsequence(actionableOrder, actualOrder),
        `Tab order should include required controls in sequence:\nexpected: ${actionableOrder.join(" → ")}\nactual:   ${actualOrder.join(" → ")}`
      ).to.be.true;
    });
  });

  it("verifies aria-labels and alt text are populated", () => {
    visitDashboard();
    cy.document().then((doc) => {
      const ariaElements = Array.from(
        doc.querySelectorAll<HTMLElement>("[aria-label]"),
      ).filter((el) => el.getAttribute("aria-hidden") !== "true");
      expect(ariaElements.length).to.be.greaterThan(0);
      const missingLabel = ariaElements.filter(
        (el) => !(el.getAttribute("aria-label") || "").trim(),
      );
      expect(missingLabel, "Elements with empty aria-label").to.have.length(0);

      const unlabeledImages = Array.from(
        doc.querySelectorAll<HTMLImageElement>("img"),
      ).filter((img) => {
        const alt = img.getAttribute("alt");
        if (img.getAttribute("aria-hidden") === "true") return false;
        if (img.getAttribute("role") === "presentation") return false;
        return !alt || !alt.trim();
      });
      expect(unlabeledImages, "Images missing alt text").to.have.length(0);

      // Verify that each *focusable* form control has an accessible name
      const isFocusableControl = (el: HTMLElement) => {
        const tag = el.tagName.toLowerCase();
        if (!["input", "select", "textarea"].includes(tag)) return false;
        if (el.getAttribute("aria-hidden") === "true") return false;
        const type = (el.getAttribute("type") || "").toLowerCase();
        if (type === "hidden") return false;
        if (el.hasAttribute("disabled")) return false;
        const win = doc.defaultView!;
        const style = win.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        return true;
      };

      const hasAccessibleName = (el: HTMLElement) => {
        // 1) aria-label present and non-empty
        const ariaLabel = el.getAttribute("aria-label");
        if (ariaLabel && ariaLabel.trim().length > 0) return true;

        // 2) aria-labelledby points to node(s) with non-empty text
        const labelledBy = el.getAttribute("aria-labelledby");
        if (labelledBy) {
          const ids = labelledBy.split(/\s+/);
          const text = ids
            .map((id) => doc.getElementById(id))
            .filter(Boolean)
            .map((n) => (n!.textContent || "").trim())
            .join(" ")
            .trim();
          if (text.length > 0) return true;
        }

        // 3) <label for="id"> association
        const id = el.getAttribute("id");
        if (id) {
          const explicit = doc.querySelector(`label[for="${id}"]`);
          if (explicit && (explicit.textContent || "").trim().length > 0) return true;
        }

        // 4) Wrapped by <label>… control …</label>
        const wrappingLabel = el.closest("label");
        if (wrappingLabel && (wrappingLabel.textContent || "").trim().length > 0) return true;

        // 5) Fallback: non-empty title attribute (acceptable but not preferred)
        const title = el.getAttribute("title");
        if (title && title.trim().length > 0) return true;

        return false;
      };

      const controls = Array.from(
        doc.querySelectorAll<HTMLElement>("input, select, textarea")
      ).filter(isFocusableControl);

      const controlsMissingLabel = controls.filter((el) => !hasAccessibleName(el));

      // Helpful diagnostics in failure output
      if (controlsMissingLabel.length > 0) {
        const details = controlsMissingLabel
          .slice(0, 10)
          .map((el) => {
            const id = el.getAttribute("id") || "(no id)";
            const name =
              el.getAttribute("aria-label") ||
              el.getAttribute("aria-labelledby") ||
              el.getAttribute("title") ||
              "(none)";
            const type = el.getAttribute("type") || el.tagName.toLowerCase();
            return `• ${type} id=${id} name=${name}`;
          })
          .join("\\n");
        // eslint-disable-next-line no-console
        console.warn("Controls missing accessible name:\\n" + details);
      }

      expect(
        controlsMissingLabel,
        "Focusable form controls missing an accessible name"
      ).to.have.length(0);
    });
  });

  it("shows visible focus indicators on auth + dashboard controls", () => {
    visitLoginScreen();
    ensureFocusIndicators([
      "form input[type='email']",
      "form input[type='password']",
      "form button[type='submit']",
      "form button[type='button']",
    ]);

    visitDashboard();
    ensureFocusIndicators([
      "[data-testid='filter-source']",
      "[data-testid='filter-metric']",
      "[data-testid='filter-start']",
      "[data-testid='filter-end']",
      "[data-testid='btn-run']",
      "[data-testid='btn-reset']",
      "[data-testid='btn-signout']",
      "[data-testid='quick-range']",
      "[data-testid='anoms-window']",
      "[data-testid='anoms-z']",
      "[data-testid='toggle-anoms']",
      "[data-testid='toggle-forecast']",
      "[data-testid='rel-badge']",
      "[data-testid='btn-export-png']",
      "[data-testid='btn-export-csv']",
    ]);
  });
});
