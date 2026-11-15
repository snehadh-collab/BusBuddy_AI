const COUPONS = [
  {
    code: "FIRST",
    title: "Flat ₹250 off first booking",
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
    code: "BLR200",
    title: "20% off up to ₹200 on Chennai–Bangalore AC Sleeper",
    type: "percent",
    value: 20,
    maxCap: 200,
    minFare: 1000,
    newUserOnly: false,
    route: "Chennai-Bangalore",
    busType: "AC Sleeper",
    payment: "ALL",
  },
  {
    code: "SLEEPER15",
    title: "15% off up to ₹180 on AC Sleeper buses",
    type: "percent",
    value: 15,
    maxCap: 180,
    minFare: 900,
    newUserOnly: false,
    route: "ALL",
    busType: "AC Sleeper",
    payment: "ALL",
  },
  {
    code: "UPI125",
    title: "Flat ₹125 cashback on UPI payments",
    type: "flat",
    value: 125,
    maxCap: 125,
    minFare: 750,
    newUserOnly: false,
    route: "ALL",
    busType: "ALL",
    payment: "UPI",
  },
  {
    code: "SAVE10",
    title: "10% off up to ₹150 on bookings above ₹800",
    type: "percent",
    value: 10,
    maxCap: 150,
    minFare: 800,
    newUserOnly: false,
    route: "ALL",
    busType: "ALL",
    payment: "ALL",
  },
];

let currentBestCode = "BLR200";

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
  buttonEl.textContent = "Copied!";
  setTimeout(() => (buttonEl.textContent = original), 1500);

  // If active tab is redbus.in, attempt to auto-fill any visible promo/coupon input field
  if (chrome && chrome.tabs) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0] && tabs[0].url && tabs[0].url.includes("redbus.in")) {
        chrome.scripting.executeScript({
          target: { tabId: tabs[0].id },
          func: (promo) => {
            const inputs = Array.from(document.querySelectorAll("input"));
            const couponBox = inputs.find((el) =>
              (el.placeholder + el.name + el.id).toLowerCase().match(/coupon|promo|offer|discount/)
            );
            if (couponBox) {
              couponBox.value = promo;
              couponBox.dispatchEvent(new Event("input", { bubbles: true }));
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