import type { GroupDraft, OptionDraft, Options, OptionValue, PluginDraft, PluginSettings, Schema } from './types.ts'

export function parseIds(text: string): string[] {
  const ids = text.trim().split(/[\s,，]+/).filter(Boolean)
  if (ids.some(id => !/^[1-9][0-9]{0,19}$/.test(id))) throw new Error('群号和 QQ 号必须是完整的正整数。')
  return [...new Set(ids)]
}

export function resolveSchema(schema: Schema, root: Schema): Schema {
  if (schema.$ref) {
    const target = root.$defs?.[schema.$ref.replace(/^#\/\$defs\//, '')]
    if (!target) throw new Error('参数引用无法解析。')
    return resolveSchema({ ...target, ...schema, $ref: undefined }, root)
  }
  if (schema.anyOf) {
    const branches = schema.anyOf.filter(item => item.type !== 'null')
    if (branches.length !== 1) throw new Error('暂不支持多类型参数，无法保存。')
    return resolveSchema({ ...resolveSchema(branches[0]!, root), ...schema, anyOf: undefined,
      nullable: schema.anyOf.some(item => item.type === 'null') }, root)
  }
  if (schema.type === 'array') {
    if (schema.nullable) throw new Error('暂不支持可空列表，无法保存。')
    const items = resolveSchema(schema.items || {}, root)
    if (!['string', 'number', 'integer', 'boolean'].includes(items.type || '')) throw new Error('暂不支持此列表元素类型。')
    return { ...schema, items }
  }
  if (!['string', 'number', 'integer', 'boolean'].includes(schema.type || '') && !schema.enum) {
    throw new Error('暂不支持此参数类型，无法保存。')
  }
  return schema
}

export function draftValue(value: OptionValue | undefined, schema: Schema): string | boolean {
  if (schema.enum || (schema.type === 'boolean' && schema.nullable)) return JSON.stringify(value ?? null)
  if (schema.type === 'boolean') return Boolean(value)
  if (schema.type === 'array') return Array.isArray(value) ? value.map(String).join('\n') : ''
  return value === null || value === undefined ? '' : String(value)
}

export function optionsToDraft(root: Schema, values: Options, sparse = false): OptionDraft {
  const output: OptionDraft = {}
  for (const [key, source] of Object.entries(root.properties || {})) {
    if (sparse && !Object.hasOwn(values, key)) continue
    // Unsupported schemas remain visible; readOptions prevents saving them.
    try {
      const schema = resolveSchema(source, root)
      output[key] = draftValue(Object.hasOwn(values, key) ? values[key] : schema.default, schema)
    } catch { output[key] = '' }
  }
  return output
}

function scalar(text: string, schema: Schema): string | number | boolean {
  if (schema.type === 'string') return text
  if (schema.type === 'boolean') {
    if (text !== 'true' && text !== 'false') throw new Error('布尔值只能填写 true 或 false。')
    return text === 'true'
  }
  const value = Number(text)
  if (!text.trim() || !Number.isFinite(value) || (schema.type === 'integer' && !Number.isSafeInteger(value))) {
    throw new Error('请输入有效数字；整数需处于浏览器可精确表示的范围。')
  }
  return value
}

export function readOptions(root: Schema, draft: OptionDraft, original: Options = {}): Options {
  // Validate all fields even when the supplied group override is sparse.
  const schemas = Object.fromEntries(Object.entries(root.properties || {}).map(([key, value]) => [key, resolveSchema(value, root)]))
  const output: Options = {}
  for (const [key, raw] of Object.entries(draft)) {
    const schema = schemas[key]
    if (!schema) throw new Error('参数已变更，请刷新后重新填写。')
    if (Object.hasOwn(original, key) && raw === draftValue(original[key], schema)) {
      const value = original[key]!
      output[key] = Array.isArray(value) ? [...value] : value
    } else if (schema.enum || (schema.type === 'boolean' && schema.nullable)) {
      output[key] = JSON.parse(String(raw)) as OptionValue
    } else if (schema.type === 'boolean') output[key] = raw === true
    else if (schema.type === 'array') {
      output[key] = raw === '' ? [] : String(raw).split(/\r?\n/).map(line =>
        scalar(schema.items!.type === 'string' ? line : line.trim(), schema.items!) )
    } else if (schema.nullable && raw === '') output[key] = null
    else output[key] = scalar(String(raw), schema)
  }
  return output
}

export function groupToDraft(id: string, settings: PluginSettings, schema: Schema, key: number): GroupDraft {
  return { key, id, memberMode: Object.hasOwn(settings.group_user_ids, id) ? 'allowlist' : 'all',
    users: (settings.group_user_ids[id] || []).join('\n'),
    options: optionsToDraft(schema, settings.group_options[id] || {}, true),
    original: settings.group_options[id] || {} }
}

export function settingsToDraft(settings: PluginSettings, schema: Schema): PluginDraft {
  return { enabled: settings.enabled, load_on_start: settings.load_on_start,
    groups: settings.group_ids.map((id, key) => groupToDraft(id, settings, schema, key)),
    privateMode: !settings.allow_private ? 'off' : settings.private_user_ids === null ? 'all' : 'allowlist',
    privateUsers: (settings.private_user_ids || []).join('\n'), options: optionsToDraft(schema, settings.options) }
}

export function readSettings(draft: PluginDraft, root: Schema, original: PluginSettings): PluginSettings {
  const ids = draft.groups.map(group => {
    const id = group.id.trim()
    if (!/^[1-9][0-9]{0,19}$/.test(id)) throw new Error('请填写有效群号，或移除空白群规则。')
    return id
  })
  if (new Set(ids).size !== ids.length) throw new Error('同一插件不能重复添加相同群号。')
  const groupUsers: Record<string, string[]> = {}
  const groupOptions: Record<string, Options> = {}
  draft.groups.forEach((group, index) => {
    const id = ids[index]!
    if (group.memberMode === 'allowlist') groupUsers[id] = parseIds(group.users)
    const overrides = readOptions(root, group.options, group.original)
    if (Object.keys(overrides).length) groupOptions[id] = overrides
  })
  return { enabled: draft.enabled, load_on_start: draft.load_on_start, group_ids: ids,
    group_user_ids: groupUsers, group_options: groupOptions, allow_private: draft.privateMode !== 'off',
    private_user_ids: draft.privateMode === 'all' ? null : draft.privateMode === 'allowlist' ? parseIds(draft.privateUsers) : original.private_user_ids,
    options: readOptions(root, draft.options, original.options) }
}
