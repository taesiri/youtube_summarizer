const defaultSchema = JSON.parse(document.getElementById("raw-schema-text").value);

const schemaFields = document.getElementById("schema-fields");
const addFieldBtn = document.getElementById("add-field");
const toggleRawBtn = document.getElementById("toggle-raw");
const inferSchemaBtn = document.getElementById("infer-schema");
const presetSelect = document.getElementById("preset-select");
const loadPresetBtn = document.getElementById("load-preset");
const savePresetBtn = document.getElementById("save-preset");
const presetNameInput = document.getElementById("preset-name");
const rawSchemaBox = document.getElementById("raw-schema");
const rawSchemaText = document.getElementById("raw-schema-text");
const schemaJsonInput = document.getElementById("schema-json");
const form = document.getElementById("summarize-form");
const progress = document.getElementById("progress");
const progressText = document.getElementById("progress-text");
const errorBox = document.getElementById("error");
const submitBtn = document.getElementById("submit-btn");
const resultCard = document.getElementById("result-card");
const resultPreview = document.getElementById("result-preview");
const resultJson = document.getElementById("result-json");
const toggleJsonBtn = document.getElementById("toggle-json");
const exportJsonBtn = document.getElementById("export-json");

const fieldTypes = ["string", "number", "boolean", "list", "object"];

function createInput(name, value = "") {
  const input = document.createElement("input");
  input.type = "text";
  input.name = name;
  input.value = value;
  return input;
}

function createSelect(options, value) {
  const select = document.createElement("select");
  for (const option of options) {
    const opt = document.createElement("option");
    opt.value = option;
    opt.textContent = option;
    if (option === value) opt.selected = true;
    select.appendChild(opt);
  }
  return select;
}

function setHidden(element, hidden) {
  if (hidden) {
    element.classList.add("hidden");
    element.setAttribute("hidden", "");
  } else {
    element.classList.remove("hidden");
    element.removeAttribute("hidden");
  }
}

function isHidden(element) {
  return element.classList.contains("hidden") || element.hasAttribute("hidden");
}

function createFieldRow(field = { name: "", type: "string", required: false, children: [] }) {
  const row = document.createElement("div");
  row.className = "field-row";

  const nameInput = createInput("name", field.name);
  nameInput.placeholder = "field_name";
  const typeSelect = createSelect(fieldTypes, field.type);

  const requiredLabel = document.createElement("label");
  requiredLabel.className = "inline";
  const requiredCheckbox = document.createElement("input");
  requiredCheckbox.type = "checkbox";
  requiredCheckbox.checked = field.required;
  requiredLabel.appendChild(requiredCheckbox);
  requiredLabel.appendChild(document.createTextNode(" required"));

  const addChildBtn = document.createElement("button");
  addChildBtn.type = "button";
  addChildBtn.textContent = "Add Nested Field";
  addChildBtn.className = "small";

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.textContent = "Remove";
  removeBtn.className = "ghost";

  const childrenWrap = document.createElement("div");
  childrenWrap.className = "nested hidden";

  addChildBtn.addEventListener("click", () => {
    childrenWrap.classList.remove("hidden");
    childrenWrap.appendChild(createFieldRow());
  });

  typeSelect.addEventListener("change", () => {
    if (typeSelect.value === "object") {
      childrenWrap.classList.remove("hidden");
    } else {
      childrenWrap.classList.add("hidden");
    }
  });

  removeBtn.addEventListener("click", () => {
    row.remove();
  });

  row.appendChild(nameInput);
  row.appendChild(typeSelect);
  row.appendChild(requiredLabel);
  row.appendChild(addChildBtn);
  row.appendChild(removeBtn);
  row.appendChild(childrenWrap);

  if (field.type === "object") {
    childrenWrap.classList.remove("hidden");
    for (const child of field.children || []) {
      childrenWrap.appendChild(createFieldRow(child));
    }
  }

  return row;
}

function collectFields(container) {
  const fields = [];
  for (const row of container.querySelectorAll(":scope > .field-row")) {
    const name = row.querySelector('input[name="name"]').value.trim();
    const type = row.querySelector("select").value;
    const required = row.querySelector('input[type="checkbox"]').checked;
    const nested = row.querySelector(".nested");

    if (!name) continue;

    const field = { name, type, required, children: [] };
    if (type === "object" && nested) {
      field.children = collectFields(nested);
    }
    fields.push(field);
  }
  return fields;
}

function schemaFromFields(fields) {
  const properties = {};
  const required = [];
  for (const field of fields) {
    let schema;
    if (field.type === "string") schema = { type: "string" };
    if (field.type === "number") schema = { type: "number" };
    if (field.type === "boolean") schema = { type: "boolean" };
    if (field.type === "list") schema = { type: "array", items: { type: "string" } };
    if (field.type === "object") {
      schema = schemaFromFields(field.children || []);
    }
    properties[field.name] = schema;
    if (field.required) required.push(field.name);
  }
  const obj = { type: "object", properties };
  if (required.length) obj.required = required;
  return obj;
}

function setSchemaJSON(schemaObj) {
  const json = JSON.stringify(schemaObj, null, 2);
  schemaJsonInput.value = json;
  rawSchemaText.value = json;
}

function buildFieldsFromSchema(schemaObj) {
  const props = schemaObj.properties || {};
  const fields = [];
  for (const [name, schema] of Object.entries(props)) {
    const type = schema.type === "array" ? "list" : schema.type || "string";
    const required = (schemaObj.required || []).includes(name);
    const field = { name, type, required, children: [] };
    if (type === "object" && schema.properties) {
      field.children = Object.entries(schema.properties).map(([childName, childSchema]) => ({
        name: childName,
        type: childSchema.type === "array" ? "list" : childSchema.type || "string",
        required: (schema.required || []).includes(childName),
        children: [],
      }));
    }
    fields.push(field);
  }
  return fields;
}

function applySchemaToBuilder(schemaObj) {
  schemaFields.innerHTML = "";
  const fields = buildFieldsFromSchema(schemaObj);
  if (fields.length === 0) {
    schemaFields.appendChild(createFieldRow());
  } else {
    for (const field of fields) {
      schemaFields.appendChild(createFieldRow(field));
    }
  }
  setSchemaJSON(schemaFromFields(collectFields(schemaFields)));
}

function initFromDefault() {
  applySchemaToBuilder(defaultSchema);
}

addFieldBtn.addEventListener("click", () => {
  schemaFields.appendChild(createFieldRow());
});

toggleRawBtn.addEventListener("click", () => {
  rawSchemaBox.classList.toggle("hidden");
  toggleRawBtn.textContent = rawSchemaBox.classList.contains("hidden")
    ? "Show Raw Schema"
    : "Hide Raw Schema";
});

rawSchemaText.addEventListener("input", () => {
  schemaJsonInput.value = rawSchemaText.value;
});

schemaFields.addEventListener("input", () => {
  const schemaObj = schemaFromFields(collectFields(schemaFields));
  setSchemaJSON(schemaObj);
});

toggleJsonBtn.addEventListener("click", () => {
  const jsonHidden = isHidden(resultJson);
  if (jsonHidden) {
    setHidden(resultJson, false);
    setHidden(resultPreview, true);
    toggleJsonBtn.textContent = "Hide Raw JSON";
  } else {
    setHidden(resultJson, true);
    setHidden(resultPreview, false);
    toggleJsonBtn.textContent = "Show Raw JSON";
  }
});

exportJsonBtn.addEventListener("click", () => {
  const content = resultJson.textContent.trim();
  if (!content) {
    return;
  }
  const blob = new Blob([content], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "summary.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setHidden(errorBox, true);
  setHidden(resultCard, true);
  progressText.textContent = "Summarizing video...";
  setHidden(progress, false);
  submitBtn.disabled = true;

  const formData = new FormData(form);
  let schema;
  try {
    schema = JSON.parse(schemaJsonInput.value);
  } catch (err) {
    errorBox.textContent = "Schema JSON is invalid. Use the builder or fix the raw JSON.";
    setHidden(errorBox, false);
    setHidden(progress, true);
    submitBtn.disabled = false;
    return;
  }

  const payload = {
    video_input: formData.get("video_input"),
    prompt: formData.get("prompt"),
    schema,
    model: formData.get("model"),
  };

  try {
    const response = await fetch("/api/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }
    resultJson.textContent = JSON.stringify(data, null, 2);
    renderPreview(data, schema);
    setHidden(resultJson, true);
    setHidden(resultPreview, false);
    toggleJsonBtn.textContent = "Show Raw JSON";
    setHidden(resultCard, false);
  } catch (err) {
    errorBox.textContent = err.message;
    setHidden(errorBox, false);
  } finally {
    setHidden(progress, true);
    submitBtn.disabled = false;
  }
});

inferSchemaBtn.addEventListener("click", async () => {
  const prompt = form.querySelector('textarea[name="prompt"]').value.trim();
  const model = form.querySelector('input[name="model"]').value.trim() || "gemini-3-flash-preview";
  if (!prompt) {
    errorBox.textContent = "Add a prompt first to infer a schema.";
    setHidden(errorBox, false);
    return;
  }

  setHidden(errorBox, true);
  progressText.textContent = "Inferring schema...";
  setHidden(progress, false);
  inferSchemaBtn.disabled = true;

  try {
    const response = await fetch("/api/infer-schema", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, model }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Schema inference failed.");
    }
    if (!data || data.type !== "object") {
      throw new Error("Model returned an invalid schema.");
    }
    applySchemaToBuilder(data);
  } catch (err) {
    errorBox.textContent = err.message;
    setHidden(errorBox, false);
  } finally {
    setHidden(progress, true);
    inferSchemaBtn.disabled = false;
  }
});

loadPresetBtn.addEventListener("click", async () => {
  const presetId = presetSelect.value;
  if (!presetId) {
    errorBox.textContent = "Choose a preset to load.";
    setHidden(errorBox, false);
    return;
  }

  setHidden(errorBox, true);
  progressText.textContent = "Loading preset...";
  setHidden(progress, false);

  try {
    const response = await fetch(`/api/presets/${presetId}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to load preset.");
    }
    const promptField = form.querySelector('textarea[name="prompt"]');
    promptField.value = data.prompt || "";
    presetNameInput.value = data.name || "";
    if (data.schema && data.schema.type === "object") {
      applySchemaToBuilder(data.schema);
    }
  } catch (err) {
    errorBox.textContent = err.message;
    setHidden(errorBox, false);
  } finally {
    setHidden(progress, true);
  }
});

savePresetBtn.addEventListener("click", async () => {
  let name = presetNameInput.value.trim();
  if (!name && presetSelect.value) {
    name = presetSelect.options[presetSelect.selectedIndex].textContent.trim();
  }
  if (!name) {
    errorBox.textContent = "Enter a preset name (or select a preset to overwrite).";
    setHidden(errorBox, false);
    return;
  }

  let schema;
  try {
    schema = JSON.parse(schemaJsonInput.value);
  } catch (err) {
    errorBox.textContent = "Schema JSON is invalid. Use the builder or fix the raw JSON.";
    setHidden(errorBox, false);
    return;
  }

  const promptField = form.querySelector('textarea[name="prompt"]');
  const payload = {
    name,
    prompt: promptField.value,
    schema,
  };

  setHidden(errorBox, true);
  progressText.textContent = "Saving preset...";
  setHidden(progress, false);

  try {
    const response = await fetch("/api/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to save preset.");
    }
    const option = document.createElement("option");
    option.value = data.id;
    option.textContent = data.name;
    presetSelect.appendChild(option);
    presetSelect.value = data.id;
  } catch (err) {
    errorBox.textContent = err.message;
    setHidden(errorBox, false);
  } finally {
    setHidden(progress, true);
  }
});

function renderPreview(data, schema) {
  resultPreview.innerHTML = "";
  const props = (schema && schema.properties) || {};
  const list = document.createElement("dl");
  list.className = "preview-list";

  for (const [key, fieldSchema] of Object.entries(props)) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    const value = data[key];
    dd.appendChild(renderValue(value, fieldSchema));
    list.appendChild(dt);
    list.appendChild(dd);
  }
  resultPreview.appendChild(list);
}

function renderValue(value, fieldSchema) {
  if (value === null || value === undefined) {
    const span = document.createElement("span");
    span.textContent = "null";
    span.className = "muted";
    return span;
  }
  if (fieldSchema.type === "array" || Array.isArray(value)) {
    const ul = document.createElement("ul");
    ul.className = "preview-list-items";
    for (const item of value) {
      const li = document.createElement("li");
      li.appendChild(renderValue(item, fieldSchema.items || {}));
      ul.appendChild(li);
    }
    return ul;
  }
  if (fieldSchema.type === "object" && typeof value === "object") {
    const nested = document.createElement("dl");
    nested.className = "preview-nested";
    const props = fieldSchema.properties || {};
    for (const [childKey, childSchema] of Object.entries(props)) {
      const dt = document.createElement("dt");
      dt.textContent = childKey;
      const dd = document.createElement("dd");
      dd.appendChild(renderValue(value[childKey], childSchema));
      nested.appendChild(dt);
      nested.appendChild(dd);
    }
    return nested;
  }
  const span = document.createElement("span");
  span.textContent = String(value);
  return span;
}

setHidden(progress, true);
setHidden(errorBox, true);
setHidden(resultCard, true);
setHidden(resultJson, true);
initFromDefault();
