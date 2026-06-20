const deviceSelect = document.getElementById("device");
const volumeSlider = document.getElementById("volume");
const stopButton = document.getElementById("stop");
const grid = document.getElementById("grid");
const emptyState = document.getElementById("empty");

const uploadModal = document.getElementById("upload-modal");
const uploadForm = document.getElementById("upload-form");
const uploadFile = document.getElementById("upload-file");
const uploadName = document.getElementById("upload-name");
const syncButton = document.getElementById("sync");
const openUploadButton = document.getElementById("open-upload");

const manageModal = document.getElementById("manage-modal");
const manageList = document.getElementById("manage-list");
const editPanel = document.getElementById("edit-panel");
const editName = document.getElementById("edit-name");
const saveEditButton = document.getElementById("save-edit");
const deleteSoundButton = document.getElementById("delete-sound");
const manageCloseOnly = document.getElementById("manage-close-only");
const openManageButton = document.getElementById("open-manage");

let sounds = [];
let selectedSound = null;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

function openModal(modal) {
  modal.hidden = false;
}

function closeModal(modal) {
  modal.hidden = true;
}

function bindModalCloseHandlers() {
  document.querySelectorAll("[data-close]").forEach((element) => {
    element.addEventListener("click", () => {
      closeModal(document.getElementById(element.dataset.close));
    });
  });
}

async function saveConfig(partial) {
  await api("/api/config", {
    method: "POST",
    body: JSON.stringify(partial),
  });
}

async function loadDevices() {
  const { devices } = await api("/api/devices");
  const config = await api("/api/config");

  deviceSelect.innerHTML = "";
  for (const device of devices) {
    const option = document.createElement("option");
    option.value = device;
    option.textContent = device;
    deviceSelect.appendChild(option);
  }

  const saved = config.device || "";
  const blackhole = devices.find((d) => d.toLowerCase().includes("blackhole"));
  deviceSelect.value =
    devices.includes(saved) ? saved : blackhole || devices[0] || "";

  if (deviceSelect.value) {
    await saveConfig({ device: deviceSelect.value });
  }

  volumeSlider.value = config.volume ?? 1;
}

function renderSoundGrid() {
  grid.innerHTML = "";

  if (sounds.length === 0) {
    emptyState.hidden = false;
    return;
  }

  emptyState.hidden = true;
  for (const sound of sounds) {
    const button = document.createElement("button");
    button.className = "sound-btn";
    button.textContent = sound.name;
    button.addEventListener("click", () => playSound(sound.id));
    grid.appendChild(button);
  }
}

function renderManageList() {
  manageList.innerHTML = "";

  if (sounds.length === 0) {
    manageList.textContent = "No sounds to manage.";
    editPanel.hidden = true;
    manageCloseOnly.hidden = false;
    selectedSound = null;
    return;
  }

  for (const sound of sounds) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "manage-item";
    if (selectedSound?.id === sound.id) {
      item.classList.add("selected");
    }
    item.textContent = sound.name;
    item.addEventListener("click", () => selectSound(sound));
    manageList.appendChild(item);
  }
}

function selectSound(sound) {
  selectedSound = sound;
  editName.value = sound.name;
  editPanel.hidden = false;
  manageCloseOnly.hidden = true;
  renderManageList();
}

async function loadSounds() {
  sounds = await api("/api/sounds");
  renderSoundGrid();
  if (!manageModal.hidden) {
    renderManageList();
    if (selectedSound) {
      const updated = sounds.find((sound) => sound.id === selectedSound.id);
      if (updated) {
        selectSound(updated);
      } else {
        selectedSound = null;
        editPanel.hidden = true;
        manageCloseOnly.hidden = false;
      }
    }
  }
}

async function playSound(id) {
  await api("/api/play", {
    method: "POST",
    body: JSON.stringify({ id }),
  });
}

openUploadButton.addEventListener("click", () => {
  uploadForm.reset();
  openModal(uploadModal);
});

openManageButton.addEventListener("click", () => {
  selectedSound = null;
  editPanel.hidden = true;
  manageCloseOnly.hidden = false;
  renderManageList();
  openModal(manageModal);
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = uploadFile.files[0];
  if (!file) {
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  if (uploadName.value.trim()) {
    formData.append("name", uploadName.value.trim());
  }

  try {
    await api("/api/sounds/upload", {
      method: "POST",
      body: formData,
    });
    closeModal(uploadModal);
    uploadForm.reset();
    await loadSounds();
  } catch (error) {
    alert(error.message);
  }
});

syncButton.addEventListener("click", async () => {
  try {
    await api("/api/sounds/sync", { method: "POST", body: "{}" });
    await loadSounds();
  } catch (error) {
    alert(error.message);
  }
});

saveEditButton.addEventListener("click", async () => {
  if (!selectedSound) {
    return;
  }

  const trimmed = editName.value.trim();
  if (!trimmed) {
    alert("Display name cannot be empty.");
    return;
  }

  try {
    await api("/api/sounds/update", {
      method: "POST",
      body: JSON.stringify({ id: selectedSound.id, name: trimmed }),
    });
    await loadSounds();
  } catch (error) {
    alert(error.message);
  }
});

deleteSoundButton.addEventListener("click", async () => {
  if (!selectedSound) {
    return;
  }

  const confirmed = confirm(`Delete "${selectedSound.name}"? This removes the file.`);
  if (!confirmed) {
    return;
  }

  try {
    await api("/api/sounds/delete", {
      method: "POST",
      body: JSON.stringify({ id: selectedSound.id }),
    });
    selectedSound = null;
    editPanel.hidden = true;
    manageCloseOnly.hidden = false;
    await loadSounds();
  } catch (error) {
    alert(error.message);
  }
});

deviceSelect.addEventListener("change", () => {
  saveConfig({ device: deviceSelect.value });
});

volumeSlider.addEventListener("input", () => {
  saveConfig({ volume: parseFloat(volumeSlider.value) });
});

stopButton.addEventListener("click", () => {
  api("/api/stop", { method: "POST", body: "{}" });
});

bindModalCloseHandlers();
loadDevices();
loadSounds();
