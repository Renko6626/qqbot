// Flat Pydantic schemas only: scalars, enums and simple lists.
export function parseIds(text) {
  const ids = text.trim().split(/[\s,，]+/).filter(Boolean);
  if (ids.some(id => !/^[1-9][0-9]{0,19}$/.test(id))) {
    throw new Error("群号和 QQ 号必须是完整的正整数。");
  }
  return [...new Set(ids)];
}

export function scalarValue(text, schema) {
  if (schema.type === "string") return text;
  if (schema.type === "boolean") {
    if (text !== "true" && text !== "false") throw new Error("布尔值只能填写 true 或 false。");
    return text === "true";
  }
  if (schema.type === "integer" || schema.type === "number") {
    if (!text.trim()) throw new Error("数字不能为空。");
    const number = Number(text);
    if (!Number.isFinite(number) || (schema.type === "integer" && !Number.isSafeInteger(number))) {
      throw new Error("请输入有效数字；整数需处于浏览器可精确表示的范围。");
    }
    return number;
  }
  throw new Error(`暂不支持的参数类型：${schema.type || "未知"}`);
}

function resolveSchema(schema, root) {
  if (schema.$ref) {
    const key = schema.$ref.replace(/^#\/\$defs\//, "");
    if (!root.$defs?.[key]) throw new Error("参数引用无法解析。");
    return {...resolveSchema(root.$defs[key], root), ...schema, $ref: undefined};
  }
  if (schema.anyOf) {
    const nonNull = schema.anyOf.filter(item => item.type !== "null");
    if (nonNull.length !== 1) throw new Error("暂不支持多类型参数。");
    return {...resolveSchema(nonNull[0], root), ...schema, anyOf: undefined,
      nullable: schema.anyOf.some(item => item.type === "null")};
  }
  return schema;
}

// Override forms return only checked fields; inherited fields never enter the payload.
export function optionsForm(container, root, values, override = null) {
  if (override) {
    const fields = [];
    for (const [name, schema] of Object.entries(root.properties || {})) {
      const section = document.createElement("div");
      section.className = "option-override";
      const toggle = document.createElement("label");
      toggle.className = "override-toggle";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Object.hasOwn(values, name);
      toggle.append(checkbox, document.createTextNode(`单独设置${schema.title || name}`));
      const state = document.createElement("span");
      state.className = "field-hint";
      const editor = document.createElement("div");
      const fieldRoot = {...root, properties: {[name]: schema}};
      let read;
      const render = source => {
        editor.replaceChildren();
        read = optionsForm(editor, fieldRoot, source);
        editor.querySelectorAll("input, select, textarea").forEach(input => { input.disabled = !checkbox.checked; });
        state.textContent = checkbox.checked ? "已覆盖；取消勾选恢复公共参数" : "继承公共参数";
      };
      render(checkbox.checked ? values : override.inherited());
      checkbox.addEventListener("change", () => {
        if (!checkbox.checked) render(override.inherited());
        else {
          editor.querySelectorAll("input, select, textarea").forEach(input => { input.disabled = false; });
          state.textContent = "已覆盖；取消勾选恢复公共参数";
        }
      });
      section.append(toggle, state, editor);
      container.append(section);
      fields.push({checkbox, read: () => read(), refresh: source => { if (!checkbox.checked) render(source); }});
    }
    const read = () => Object.assign({}, ...fields.filter(field => field.checkbox.checked).map(field => field.read()));
    read.refresh = () => {
      const source = override.inherited();
      fields.forEach(field => field.refresh(source));
    };
    return read;
  }
  const readers = new Map();
  for (const [name, original] of Object.entries(root.properties || {})) {
    const schema = resolveSchema(original, root);
    const label = document.createElement("label");
    label.className = "field";
    label.append(document.createTextNode(schema.title || name));
    let input;
    let read;
    const value = Object.hasOwn(values, name) ? values[name] : schema.default;
    if (schema.enum || (schema.type === "boolean" && schema.nullable)) {
      input = document.createElement("select");
      const choices = [...(schema.enum || [true, false])];
      if (schema.nullable && !choices.includes(null)) choices.unshift(null);
      for (const choice of choices) {
        const option = document.createElement("option");
        option.value = JSON.stringify(choice);
        option.textContent = choice === null ? "不设置" : String(choice);
        input.append(option);
      }
      input.value = JSON.stringify(value ?? null);
      read = () => JSON.parse(input.value);
    } else if (schema.type === "boolean") {
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(value);
      read = () => input.checked;
    } else if (schema.type === "array") {
      if (schema.nullable) throw new Error(`参数 ${name} 请使用空列表作为默认值，暂不支持可空列表。`);
      const items = resolveSchema(schema.items || {}, root);
      if (!["string", "number", "integer", "boolean"].includes(items.type)) {
        throw new Error(`参数 ${name} 的列表元素类型尚不支持。`);
      }
      input = document.createElement("textarea");
      input.rows = 3;
      input.placeholder = "每行一个值";
      input.value = (value || []).map(item => String(item)).join("\n");
      const initialText = input.value;
      read = () => {
        if (input.value === initialText) return [...(value || [])];
        if (input.value === "") return [];
        return input.value.split(/\r?\n/).map(item =>
          scalarValue(items.type === "string" ? item : item.trim(), items));
      };
    } else {
      if (!["string", "integer", "number"].includes(schema.type)) {
        throw new Error(`参数 ${name} 的类型尚不支持，未开放保存。`);
      }
      input = document.createElement("input");
      input.type = schema.type === "string" ? "text" : "number";
      if (input.type === "number") input.step = schema.type === "integer" ? "1" : "any";
      if (schema.minimum !== undefined) input.min = schema.minimum;
      if (schema.maximum !== undefined) input.max = schema.maximum;
      if (schema.minLength !== undefined) input.minLength = schema.minLength;
      if (schema.maxLength !== undefined) input.maxLength = schema.maxLength;
      input.required = !schema.nullable && (root.required?.includes(name) || schema.minLength > 0);
      input.value = value ?? "";
      const initialText = input.value;
      read = () => input.value === initialText && value !== undefined ? value :
        (schema.nullable && input.value === "" ? null : scalarValue(input.value, schema));
    }
    label.append(input);
    if (schema.description) {
      const hint = document.createElement("span");
      hint.className = "field-hint";
      hint.textContent = schema.description;
      label.append(hint);
    }
    container.append(label);
    readers.set(name, read);
  }
  return () => Object.fromEntries([...readers].map(([name, read]) => [name, read()]));
}
