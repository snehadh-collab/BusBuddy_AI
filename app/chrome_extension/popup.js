const COUPONS = [
  {
    code: "CASH300",
    title: "Up to ₹300 off on Karnataka, Tamil Nadu & Kerala routes",
    type: "percent",
    value: 20,
    maxCap: 300,
    minFare: 500,
    newUserOnly: false,
    route: "Chennai-Bangalore",
    busType: "ALL",
    payment: "ALL",
  },
  {
    code: "PRIMODAY",
    title: "Up to ₹200 off on Primo / AC Sleeper operators",
    type: "percent",
    value: 15,
    maxCap: 200,
    minFare: 800,
    newUserOnly: false,
    route: "ALL",
    busType: "AC Sleeper",
    payment: "ALL",
  },
  {
    code: "FIRST",
    title: "Up to ₹250 off on first bus booking (New Users)",
    type: "flat",
    value: 250,
    maxCap: 250,
    minFare: 500,
    newUserOnly: true,
    route: "ALL",
    busType: "ALL",
    payment: "ALL",
  },
  {
    code: "FESTIVE300",
    title: "Up to ₹300 off on bus tickets (Limited Sale)",
    type: "percent",
    value: 12,
    maxCap: 300,
    minFare: 600,
    newUserOnly: false,
    route: "ALL",
    busType: "ALL",
    payment: "ALL",
  },
  {
    code: "RED500",
    title: "10% off up to ₹250 + cashback on bus tickets",
    type: "percent",
    value: 10,
    maxCap: 250,
    minFare: 700,
    newUserOnly: false,
    route: "ALL",
    busType: "ALL",
    payment: "ALL",
  },
];

let currentBestCode = "CASH300";

function evaluateCoupons() {
  const perSeat = parseFloat(document.getElementById("fareInput").value) || 0;
  const seats = parseInt(document.getElementById("seatsInput").value, 10) || 1;
  const totalFare = perSeat * seats;
  const userType = document.getElementById("userType").value;
  const busType = document.getElementById("busType").value;
  const payment = document.getElementById("paymentMethod").value;
  const route = document.getElementById("routeSelect").value;

  const evaluated = COUPONS.map((c) => {
    let reason = "";
    if (totalFare < c.minFare) {
      reason = `Requires min fare ₹${c.minFare}`;
    } else if (c.newUserOnly && userType !== "new") {
      reason = "New users only";
    } else if (c.route !== "ALL" && c.route !== route) {
      reason = `Valid only on ${c.route}`;
    } else if (c.busType !== "ALL" && c.busType !== busType) {
      reason = `Valid only for ${c.busType}`;
    } else if (c.payment !== "ALL" && c.payment !== payment) {
      reason = `Requires ${c.payment} payment`;
    }

    if (reason) {
      return { ...c, eligible: false, discount: 0, reason };
    }

    const raw = c.type === "flat" ? c.value : (totalFare * c.value) / 100;
    const discount = Math.min(Math.round(raw), c.maxCap);
    return { ...c, eligible: true, discount, reason: "Eligible" };
  });

  const eligible = evaluated.filter((x) => x.eligible).sort((a, b) => b.discount - a.discount);
  const ineligible = evaluated.filter((x) => !x.eligible);

  const saveEl = document.getElementById("saveAmount");
  const applyEl = document.getElementById("applyText");
  const copyBtn = document.getElementById("copyBestBtn");

  if (eligible.length > 0) {
    const best = eligible[0];
    currentBestCode = best.code;
    const finalFare = Math.max(0, totalFare - best.discount);
    saveEl.textContent = `Save ₹${best.discount}`;
    applyEl.innerHTML = `Apply <span class="code-pill">${best.code}</span> at checkout. Pay <b>₹${finalFare}</b> instead of ₹${totalFare}.`;
    copyBtn.style.display = "inline-block";
  } else {
    currentBestCode = "";
    saveEl.textContent = "Save ₹0";
    applyEl.textContent = `No coupon eligible for ₹${totalFare} with current filters.`;
    copyBtn.style.display = "none";
  }

  document.getElementById("eligibleHeader").textContent = `Eligible offers (${eligible.length}) • Ineligible (${ineligible.length})`;
  const listEl = document.getElementById("offersList");
  listEl.innerHTML = "";

  [...eligible, ...ineligible].forEach((item) => {
    const div = document.createElement("div");
    div.className = `offer-item ${item.eligible ? "" : "ineligible"}`;
    div.innerHTML = `
      <div>
        <strong>${item.code}</strong> — ${item.title}
        <div class="offer-desc">${item.eligible ? `Saves ₹${item.discount}` : `Unavailable: ${item.reason}`}</div>
      </div>
      ${
        item.eligible
          ? `<button class="mini-copy" data-code="${item.code}">Copy</button>`
          : `<span style="font-size:10.5px;color:#71717A;">Locked</span>`
      }
    `;
    listEl.appendChild(div);
  });

  document.querySelectorAll(".mini-copy").forEach((btn) => {
    btn.addEventListener("click", () => copyAndInjectCode(btn.dataset.code, btn));
  });
}

function copyAndInjectCode(code, buttonEl) {
  if (!code) return;
  navigator.clipboard.writeText(code);
  const original = buttonEl.textContent;
  buttonEl.textContent = "Applied!";
  setTimeout(() => (buttonEl.textContent = original), 1500);

  if (chrome && chrome.tabs) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0] && tabs[0].url && tabs[0].url.includes("redbus.in")) {
        chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          func: (promo) => {
            // Find the RedBus coupon input box (even if React-controlled)
            const inputs = Array.from(document.querySelectorAll("input"));
            const couponBox = inputs.find((el) =>
              (el.placeholder + el.name + el.id + el.ariaLabel).toLowerCase().match(/coupon|promo|offer|discount/)
            );
            if (couponBox) {
              const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
              nativeSetter.call(couponBox, promo);
              couponBox.dispatchEvent(new Event("input", { bubbles: true }));
              couponBox.dispatchEvent(new Event("change", { bubbles: true }));

              // Click the Apply button next to the coupon input if visible
              const buttons = Array.from(document.querySelectorAll("button, span, div"));
              const applyBtn = buttons.find((b) => b.textContent.trim().toLowerCase() === "apply");
              if (applyBtn) applyBtn.click();
            }
          },
          args: [code],
        });
      }
    });
  }
}

document.getElementById("copyBestBtn").addEventListener("click", function () {
  copyAndInjectCode(currentBestCode, this);
});

["fareInput", "seatsInput", "userType", "busType", "paymentMethod", "routeSelect"].forEach((id) => {
  document.getElementById(id).addEventListener("input", evaluateCoupons);
  document.getElementById(id).addEventListener("change", evaluateCoupons);
});

evaluateCoupons();