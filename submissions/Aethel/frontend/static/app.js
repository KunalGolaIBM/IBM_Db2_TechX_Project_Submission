const profileForm = document.querySelector("#profile-form");
const taskForm = document.querySelector("#task-form");
const reviewForm = document.querySelector("#review-form");
const toast = document.querySelector("#toast");
const serviceAlert = document.querySelector("#service-alert");
let profile = null;
let toastTimer;
let db2Ready = false;
let localMode = false;

async function api(url, options = {}) {
  const headers = { Accept: "application/json", ...options.headers };
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(url, { ...options, headers, credentials: "same-origin" });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const reason = typeof result.detail === "string" ? result.detail : "Please try again in a moment.";
    throw new Error(reason);
  }
  return result;
}

function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 4300);
}

function setServiceAlert(message) {
  if (!serviceAlert) return;
  const servicePage = document.body.classList.contains("page-prototype")
    || document.body.classList.contains("page-community");
  if (!servicePage) message = "";
  serviceAlert.textContent = message;
  serviceAlert.hidden = !message;
}

function populateTimeZones() {
  const select = document.querySelector("#time-zone");
  if (!select) return;
  const guessed = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const zones = [...new Set([guessed, "UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Asia/Kolkata"])];
  zones.forEach((zone) => {
    const option = document.createElement("option");
    option.value = zone;
    option.textContent = zone.replaceAll("_", " ");
    select.append(option);
  });
  select.value = guessed;
}

function setProfile(profileData) {
  profile = profileData;
  if (!profileForm) return;
  profileForm.elements.namedItem("name").value = profile.name;
  const timeZoneSelect = profileForm.elements.namedItem("time_zone");
  if (![...timeZoneSelect.options].some((option) => option.value === profile.time_zone)) {
    const option = document.createElement("option");
    option.value = profile.time_zone;
    option.textContent = profile.time_zone;
    timeZoneSelect.append(option);
  }
  timeZoneSelect.value = profile.time_zone;
  profileForm.elements.namedItem("check_ins_enabled").checked = profile.check_ins_enabled;
  setDefaultDueDate();
}

function setDefaultDueDate() {
  if (!taskForm) return;
  const input = taskForm.elements.namedItem("due_at");
  const timeZone = profile?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(Date.now() + 60 * 60 * 1000));
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  input.value = `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`;
}

function formatDue(value) {
  return new Intl.DateTimeFormat(undefined, {
    timeZone: profile?.time_zone || undefined,
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function renderTasks(tasks) {
  const list = document.querySelector("#task-list");
  if (!list) return;
  list.replaceChildren();
  const pending = tasks.filter((task) => task.status === "pending");
  if (!pending.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = profile ? "No reminders yet. Add one whenever you like." : "Set up your profile to add a reminder.";
    list.append(empty);
    return;
  }

  pending.forEach((task) => {
    const item = document.createElement("article");
    item.className = "task-item";
    const dot = document.createElement("span");
    dot.className = "task-indicator";
    const copy = document.createElement("div");
    copy.className = "task-item-copy";
    const title = document.createElement("div");
    title.className = "task-item-title";
    title.textContent = task.description;
    const meta = document.createElement("div");
    meta.className = "task-item-meta";
    meta.textContent = `${task.task_type === "pill" ? "PILL REMINDER" : "HEALTH CHECK-IN"} · ${formatDue(task.due_at)}`;
    copy.append(title, meta);
    const done = document.createElement("button");
    done.className = "task-done";
    done.type = "button";
    done.textContent = "Done";
    done.setAttribute("aria-label", `Mark reminder complete: ${task.description}`);
    done.addEventListener("click", async () => {
      done.disabled = true;
      try {
        await api(`/api/tasks/${encodeURIComponent(task.id)}/complete`, { method: "POST" });
        await loadTasks();
        showToast("Reminder marked complete.");
      } catch (error) {
        done.disabled = false;
        showToast(error.message);
      }
    });
    item.append(dot, copy, done);
    list.append(item);
  });
}

function renderReview(review, prepend = false) {
  const board = document.querySelector("#review-board");
  if (!board) return;
  const empty = board.querySelector(".empty-state");
  if (empty) empty.remove();
  const note = document.createElement("article");
  note.className = "review-note";
  const message = document.createElement("p");
  message.textContent = review.message;
  const attribution = document.createElement("footer");
  const name = document.createElement("span");
  name.textContent = review.name;
  const date = document.createElement("time");
  date.dateTime = review.created_at;
  date.textContent = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(review.created_at));
  attribution.append(name, date);
  note.append(message, attribution);
  if (prepend) board.prepend(note);
  else board.append(note);
}

async function loadTasks() {
  renderTasks(await api("/api/tasks"));
}

async function checkDueReminders() {
  if (!profile || (!db2Ready && !localMode) || document.hidden || !taskForm) return;
  try {
    const due = await api("/api/reminders/due");
    due.forEach((task) => {
      const label = task.task_type === "pill" ? "Pill reminder" : "Health check-in";
      showToast(`${label}: ${task.description}`);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(`Aethel · ${label}`, { body: task.description });
      }
    });
    if (due.length) await loadTasks();
  } catch (error) {
    setServiceAlert(error.message);
  }
}

async function loadPrototypeWorkspace() {
  if (!profileForm) return;
  const [profileData, tasks] = await Promise.all([
    api("/api/profile"),
    api("/api/tasks"),
  ]);
  if (profileData.name) setProfile(profileData);
  renderTasks(tasks);
  await checkDueReminders();
}

async function loadCommunityBoard() {
  const board = document.querySelector("#review-board");
  if (!board) return;
  const reviews = await api("/api/reviews");
  board.replaceChildren();
  if (!reviews.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Be the first to leave a kind note for the community.";
    board.append(empty);
    return;
  }
  reviews.forEach((review) => renderReview(review));
}

profileForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(profileForm);
  const submit = profileForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const saved = await api("/api/profile", {
      method: "PUT",
      body: JSON.stringify({
        name: data.get("name"),
        time_zone: data.get("time_zone"),
        check_ins_enabled: data.get("check_ins_enabled") === "on",
      }),
    });
    setProfile(saved);
    await loadTasks();
    const feedback = document.querySelector("#profile-feedback");
    feedback.textContent = "Preferences saved to your private session.";
    showToast("Your preferences have been saved.");
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});

taskForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  // Onboarding is required because the saved time zone is used to interpret
  // the reminder's local date/time. Guide the user to the profile form rather
  // than sending a request that is guaranteed to fail with HTTP 409.
  if (!profile?.name || !profile?.time_zone) {
    showToast("Please complete and save your profile preferences first.");
    const nameField = profileForm?.elements.namedItem("name");
    if (nameField) {
      nameField.focus();
      profileForm.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    return;
  }

  const data = new FormData(taskForm);
  const submit = taskForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        task_type: data.get("task_type"),
        description: data.get("description"),
        due_at: data.get("due_at"),
      }),
    });
    taskForm.elements.namedItem("description").value = "";
    await loadTasks();
    showToast("Your reminder has been added.");
  } catch (error) {
    if (error.message.toLowerCase().includes("complete onboarding")) {
      // The server is authoritative. If its session has no profile, refresh
      // the local state and direct the user to complete onboarding again.
      profile = null;
      showToast("Your profile was not found in this session. Please save your preferences again, then retry.");
      const nameField = profileForm?.elements.namedItem("name");
      if (nameField) {
        nameField.focus();
        profileForm.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } else {
      showToast(error.message);
    }
  } finally {
    submit.disabled = false;
  }
});

reviewForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(reviewForm);
  const submit = reviewForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const review = await api("/api/reviews", {
      method: "POST",
      body: JSON.stringify({ name: data.get("name"), message: data.get("message") }),
    });
    renderReview(review, true);
    reviewForm.reset();
    const count = document.querySelector("#review-count");
    if (count) count.textContent = "0 / 320";
    showToast("Your note is on the community board.");
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});

document.querySelector("#enable-notifications")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  if (!("Notification" in window)) {
    showToast("This browser does not support desktop notifications.");
    return;
  }
  try {
    const permission = await Notification.requestPermission();
    button.textContent = permission === "granted" ? "Notifications enabled" : "Permission not granted";
    showToast(permission === "granted" ? "Browser reminders are enabled while Aethel is open." : "You can still see reminders here while Aethel is open.");
  } catch (error) {
    showToast(`Notification permission was unavailable: ${error.message}`);
  }
});

function initializeStickyNotes() {
  const board = document.querySelector(".sticky-board");
  if (!board) return;

  let activeDrag = null;
  let isPeeling = false;

  function updateStack() {
    [...board.querySelectorAll(".sticky-note")].forEach((note, index) => {
      note.style.setProperty("--stack-x", `${index * 9}px`);
      note.style.setProperty("--stack-y", `${index * 8}px`);
      note.style.setProperty("--stack-rotation", `${index % 2 ? 2 : -1}deg`);
      note.style.setProperty("--stack-scale", `${1 - index * 0.035}`);
      note.style.zIndex = String(board.children.length - index);
      note.tabIndex = index === 0 ? 0 : -1;
      note.setAttribute("aria-hidden", String(index !== 0));
    });
  }

  function resetDrag(note) {
    note.style.removeProperty("--drag-x");
    note.style.removeProperty("--drag-y");
    note.style.removeProperty("--drag-rotation");
  }

  function peel(note, deltaX = 0, deltaY = 0) {
    if (isPeeling || note !== board.firstElementChild) return;
    isPeeling = true;
    board.classList.add("is-busy");
    const side = deltaX === 0 ? (Math.random() < 0.5 ? -1 : 1) : Math.sign(deltaX);
    note.style.setProperty("--peel-x", `${side * Math.max(130, Math.abs(deltaX) + 100)}px`);
    note.style.setProperty("--peel-y", `${Math.max(120, deltaY + 120)}px`);
    note.style.setProperty("--peel-rotation", `${side * (18 + Math.random() * 15)}deg`);
    note.classList.add("is-peeling");
    note.setAttribute("aria-hidden", "true");

    const finishPeel = () => {
      note.removeEventListener("transitionend", onTransitionEnd);
      note.classList.remove("is-peeling");
      note.style.removeProperty("--peel-x");
      note.style.removeProperty("--peel-y");
      note.style.removeProperty("--peel-rotation");
      resetDrag(note);
      board.append(note);
      updateStack();
      board.classList.remove("is-busy");
      isPeeling = false;
    };
    const onTransitionEnd = (event) => {
      if (event.target === note && event.propertyName === "transform") finishPeel();
    };
    note.addEventListener("transitionend", onTransitionEnd);
    window.setTimeout(() => {
      if (isPeeling && note.classList.contains("is-peeling")) finishPeel();
    }, 750);
  }

  board.addEventListener("pointerdown", (event) => {
    const note = event.target.closest(".sticky-note");
    if (!note || note !== board.firstElementChild || isPeeling || event.button !== 0) return;
    activeDrag = { note, pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, moved: false };
    note.focus({ preventScroll: true });
    note.setPointerCapture(event.pointerId);
  });

  board.addEventListener("pointermove", (event) => {
    if (!activeDrag || event.pointerId !== activeDrag.pointerId) return;
    const deltaX = event.clientX - activeDrag.startX;
    const deltaY = event.clientY - activeDrag.startY;
    if (!activeDrag.moved && Math.hypot(deltaX, deltaY) > 8) activeDrag.moved = true;
    if (!activeDrag.moved) return;
    activeDrag.note.style.setProperty("--drag-x", `${deltaX}px`);
    activeDrag.note.style.setProperty("--drag-y", `${deltaY}px`);
    activeDrag.note.style.setProperty("--drag-rotation", `${deltaX * 0.055}deg`);
  });

  board.addEventListener("pointerup", (event) => {
    if (!activeDrag || event.pointerId !== activeDrag.pointerId) return;
    const drag = activeDrag;
    activeDrag = null;
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (drag.moved && Math.hypot(deltaX, deltaY) > 62) {
      drag.note.dataset.suppressClick = "true";
      window.setTimeout(() => delete drag.note.dataset.suppressClick, 500);
      peel(drag.note, deltaX, deltaY);
    } else if (drag.moved) {
      resetDrag(drag.note);
    }
  });

  board.addEventListener("pointercancel", () => {
    if (!activeDrag) return;
    resetDrag(activeDrag.note);
    activeDrag = null;
  });

  board.addEventListener("click", (event) => {
    const note = event.target.closest(".sticky-note");
    if (!note || note !== board.firstElementChild) return;
    if (note.dataset.suppressClick) {
      delete note.dataset.suppressClick;
      return;
    }
    peel(note);
  });

  board.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    const note = event.target.closest(".sticky-note");
    if (!note || note !== board.firstElementChild) return;
    event.preventDefault();
    peel(note);
  });

  updateStack();
}

const reviewMessage = document.querySelector("#review-message");
reviewMessage?.addEventListener("input", () => {
  document.querySelector("#review-count").textContent = `${reviewMessage.value.length} / 320`;
});

function initializeBook() {
  const book = document.querySelector("#architecture-book");
  if (!book) return;
  const sources = [...document.querySelectorAll(".book-source-page")];
  const cover = document.querySelector(".book-cover-source");
  const leftPage = document.querySelector("#book-left-page");
  const rightPage = document.querySelector("#book-right-page");
  const leaf = document.querySelector("#book-leaf");
  const front = document.querySelector("#book-leaf-front");
  const back = document.querySelector("#book-leaf-back");
  const previous = document.querySelector("#book-prev");
  const next = document.querySelector("#book-next");
  const counter = document.querySelector("#book-page-count");
  if (!sources.length || !cover || !leftPage || !rightPage || !leaf || !front || !back || !previous || !next || !counter) return;

  let current = 0;
  let turning = false;
  let pointerStart = null;

  function showSource(target, source) {
    target.replaceChildren(source.cloneNode(true));
  }

  function render() {
    showSource(leftPage, current === 0 ? cover : sources[current - 1]);
    showSource(rightPage, sources[current]);
    counter.textContent = `Page ${current + 1} of ${sources.length}`;
    previous.disabled = current === 0 || turning;
    next.disabled = current === sources.length - 1 || turning;
  }

  function turn(direction) {
    if (turning || (direction > 0 && current >= sources.length - 1) || (direction < 0 && current <= 0)) return;
    turning = true;
    showSource(front, sources[current]);
    showSource(back, sources[current + direction]);
    leaf.classList.remove("is-turning-forward", "is-turning-back");
    void leaf.offsetWidth;
    leaf.classList.add(direction > 0 ? "is-turning-forward" : "is-turning-back");
    previous.disabled = true;
    next.disabled = true;
    leaf.addEventListener("animationend", () => {
      current += direction;
      turning = false;
      leaf.classList.remove("is-turning-forward", "is-turning-back");
      render();
    }, { once: true });
  }

  previous.addEventListener("click", () => turn(-1));
  next.addEventListener("click", () => turn(1));
  book.addEventListener("dragstart", (event) => event.preventDefault());
  book.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || !event.target.closest(".book-page, .book-leaf")) return;
    pointerStart = { x: event.clientX, y: event.clientY };
  });
  book.addEventListener("pointerup", (event) => {
    if (pointerStart === null) return;
    const distance = event.clientX - pointerStart.x;
    const verticalDistance = event.clientY - pointerStart.y;
    pointerStart = null;
    if (Math.abs(distance) > 55 && Math.abs(distance) > Math.abs(verticalDistance) * 1.25) {
      turn(distance < 0 ? 1 : -1);
    }
  });
  book.addEventListener("pointercancel", () => { pointerStart = null; });
  document.addEventListener("keydown", (event) => {
    if (!document.body.classList.contains("page-architecture") || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.target.matches("input, textarea, select, button, a")) return;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      turn(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      turn(-1);
    }
  });
  render();
}

async function initializeServices() {
  const indicator = document.querySelector("#db2-indicator");
  const copy = document.querySelector("#service-copy");
  try {
    const service = await api("/api/status");
    db2Ready = service.db2_ready;
    localMode = service.local_mode || service.storage_mode === "local";
    if (indicator) indicator.classList.toggle("is-ready", db2Ready || localMode);
    if (copy) {
      copy.textContent = localMode
        ? "Local memory · session only"
        : db2Ready
          ? "Local Db2 · connected"
          : "Local Db2 · not connected";
    }
    if (!db2Ready && !localMode) {
      setServiceAlert("Connect IBM Db2 to use profile storage, reminders, and community notes. Set DB2_PASSWORD in .env, then run python -m backend.init_db.");
      if (profileForm) renderTasks([]);
      return;
    }
    setServiceAlert("");
    if (profileForm) await loadPrototypeWorkspace();
    if (reviewForm) await loadCommunityBoard();
  } catch (error) {
    if (copy) copy.textContent = "Service status unavailable";
    setServiceAlert(error.message);
    if (reviewForm) {
      const board = document.querySelector("#review-board");
      board.replaceChildren();
      const message = document.createElement("p");
      message.className = "empty-state";
      message.textContent = "Community notes are unavailable until the service reconnects.";
      board.append(message);
    }
  }
}

populateTimeZones();
setDefaultDueDate();
initializeBook();
initializeStickyNotes();
initializeServices();
if (taskForm) setInterval(checkDueReminders, 30_000);
