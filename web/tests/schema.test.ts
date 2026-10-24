import { test } from 'node:test'
import assert from 'node:assert/strict'
import { optionsToDraft, parseIds, readOptions, readSettings, settingsToDraft } from '../src/schema.ts'
import type { PluginSettings, Schema } from '../src/types.ts'

const schema: Schema = { properties: {
  enabled: { type: 'boolean', default: true }, count: { type: 'integer', default: 2 },
  labels: { type: 'array', items: { type: 'string' }, default: ['default'] },
  note: { anyOf: [{ type: 'string' }, { type: 'null' }], default: 'public' },
} }

test('IDs remain complete strings and duplicates are removed', () => {
  assert.deepEqual(parseIds('9007199254740993，12345\n12345'), ['9007199254740993', '12345'])
  assert.throws(() => parseIds('123.5'), /正整数/)
})

test('options preserve explicit false, zero, empty lists and null', () => {
  const draft = optionsToDraft(schema, {})
  draft.enabled = false; draft.count = '0'; draft.labels = ''; draft.note = ''
  assert.deepEqual(readOptions(schema, draft), { enabled: false, count: 0, labels: [], note: null })
  const original = { labels: ['', 'line\ninside'] }
  assert.deepEqual(readOptions(schema, optionsToDraft(schema, original, true), original), original)
  assert.throws(() => readOptions(schema, { count: '9007199254740993' }), /有效数字/)
})

test('group settings submit only explicit overrides and preserve whitelist semantics', () => {
  const original: PluginSettings = { enabled: true, load_on_start: true,
    group_ids: ['12345', '67890'], group_user_ids: { '12345': [] }, allow_private: false,
    private_user_ids: ['11111'], options: { enabled: true, count: 2, labels: ['default'], note: 'public' },
    group_options: { '12345': { enabled: false, count: 0, labels: [], note: null } } }
  const draft = settingsToDraft(original, schema)
  assert.deepEqual(readSettings(draft, schema, original), original)
  delete draft.groups[0]!.options.count
  draft.options.count = '9'
  draft.privateMode = 'allowlist'; draft.privateUsers = ''
  const saved = readSettings(draft, schema, original)
  assert.deepEqual(saved.group_options, { '12345': { enabled: false, labels: [], note: null } })
  assert.equal(saved.options.count, 9)
  assert.deepEqual(saved.group_user_ids, { '12345': [] })
  assert.equal(saved.allow_private, true)
  assert.deepEqual(saved.private_user_ids, [])
})

test('unsupported schemas block saving, including nullable lists', () => {
  assert.throws(() => readOptions({ properties: { nested: { type: 'object' } } }, {}), /暂不支持/)
  assert.throws(() => readOptions({ properties: { values: { anyOf: [
    { type: 'array', items: { type: 'string' } }, { type: 'null' },
  ] } } }, {}), /可空列表/)
})
