document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) {
    return;
  }
  const action = form.getAttribute("action") || "";
  if (action.includes("/commit")) {
    const ok = window.confirm("确认将该批次写入正式订单明细表？写入后不能物理删除。");
    if (!ok) {
      event.preventDefault();
    }
  }
});

const pad = (value) => String(value).padStart(2, "0");
const formatDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const startOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1);
const endOfMonth = (date) => new Date(date.getFullYear(), date.getMonth() + 1, 0);
const addDays = (date, days) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
const addMonths = (date, months) => new Date(date.getFullYear(), date.getMonth() + months, 1);

function presetRange(name) {
  const today = new Date();
  const currentMonth = startOfMonth(today);
  const day = today.getDay() || 7;
  if (name === "last7") return [addDays(today, -6), today];
  if (name === "last30") return [addDays(today, -29), today];
  if (name === "lastWeek") {
    const start = addDays(today, -day - 6);
    return [start, addDays(start, 6)];
  }
  if (name === "thisMonth") return [currentMonth, today];
  if (name === "lastMonth") {
    const start = addMonths(currentMonth, -1);
    return [start, endOfMonth(start)];
  }
  if (name === "thisQuarter") {
    const quarterStartMonth = Math.floor(today.getMonth() / 3) * 3;
    return [new Date(today.getFullYear(), quarterStartMonth, 1), today];
  }
  if (name === "firstHalf") return [new Date(today.getFullYear(), 0, 1), new Date(today.getFullYear(), 5, 30)];
  if (name === "secondHalf") return [new Date(today.getFullYear(), 6, 1), new Date(today.getFullYear(), 11, 31)];
  if (name === "lastYear") return [addDays(today, -364), today];
  if (name === "thisYear") return [new Date(today.getFullYear(), 0, 1), today];
  return [today, today];
}

function submitFilter(form) {
  if (!form) return;
  if (form.requestSubmit) {
    form.requestSubmit();
  } else {
    form.submit();
  }
}

document.querySelectorAll("[data-date-range]").forEach((root) => {
  const form = root.closest("form");
  const popover = root.querySelector("[data-date-popover]");
  const toggle = root.querySelector("[data-date-toggle]");
  const label = root.querySelector("[data-date-label]");
  const startInput = root.querySelector("[data-date-start]");
  const endInput = root.querySelector("[data-date-end]");
  const startPicker = root.querySelector("[data-date-start-picker]");
  const endPicker = root.querySelector("[data-date-end-picker]");

  const syncLabel = () => {
    label.textContent = `${startInput.value} 至 ${endInput.value}`;
    startPicker.value = startInput.value;
    endPicker.value = endInput.value;
  };

  toggle.addEventListener("click", () => {
    popover.classList.toggle("open");
  });

  root.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      const [start, end] = presetRange(button.dataset.preset);
      startInput.value = formatDate(start);
      endInput.value = formatDate(end);
      syncLabel();
      popover.classList.remove("open");
      submitFilter(form);
    });
  });

  root.querySelector("[data-date-apply]").addEventListener("click", () => {
    if (startPicker.value && endPicker.value) {
      startInput.value = startPicker.value;
      endInput.value = endPicker.value;
      syncLabel();
      popover.classList.remove("open");
      submitFilter(form);
    }
  });

  root.querySelector("[data-date-cancel]").addEventListener("click", () => {
    popover.classList.remove("open");
  });

  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) {
      popover.classList.remove("open");
    }
  });

  syncLabel();
});

document.querySelectorAll(".auto-filter").forEach((form) => {
  let timer = null;
  form.querySelectorAll("input:not([type='hidden'])").forEach((input) => {
    if (input.closest("[data-date-range]")) return;
    input.addEventListener("change", () => submitFilter(form));
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        submitFilter(form);
      }
    });
    input.addEventListener("blur", () => {
      clearTimeout(timer);
      timer = setTimeout(() => submitFilter(form), 120);
    });
  });
});
