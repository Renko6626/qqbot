<script setup lang="ts">
import { computed, useId } from 'vue'
import { resolveSchema, draftValue } from '../schema'
import type { OptionDraft, Schema } from '../types'

const props = withDefaults(defineProps<{ schema: Schema; modelValue: OptionDraft; inherited?: OptionDraft; overrides?: boolean }>(), { overrides: false })
const emit = defineEmits<{ 'update:modelValue': [value: OptionDraft] }>()
const prefix = useId()
const fields = computed(() => Object.entries(props.schema.properties || {}).map(([name, schema]) => {
  try { return { name, schema: resolveSchema(schema, props.schema), error: '' } }
  catch (error) { return { name, schema, error: (error as Error).message } }
}))
const owns = (name: string) => Object.hasOwn(props.modelValue, name)
const value = (name: string, schema: Schema) => owns(name) ? props.modelValue[name] : props.inherited?.[name] ?? draftValue(schema.default, schema)
function update(name: string, raw: string | boolean) { emit('update:modelValue', { ...props.modelValue, [name]: raw }) }
function toggle(name: string, schema: Schema, enabled: boolean) {
  const next = { ...props.modelValue }
  if (enabled) next[name] = value(name, schema) ?? ''
  else delete next[name]
  emit('update:modelValue', next)
}
const text = (event: Event) => (event.target as HTMLInputElement).value
const checked = (event: Event) => (event.target as HTMLInputElement).checked
function choices(schema: Schema) {
  const values = [...(schema.enum || [true, false])]
  if (schema.nullable && !values.includes(null)) values.unshift(null)
  return values
}
</script>

<template>
  <div class="option-grid">
    <div v-for="field in fields" :key="field.name" class="option-field" :class="{ 'inherited-field': overrides && !owns(field.name) }">
      <label v-if="overrides" class="override-label">
        <input type="checkbox" :checked="owns(field.name)" @change="toggle(field.name, field.schema, checked($event))">
        单独设置{{ field.schema.title || field.name }}
      </label>
      <p v-if="field.error" class="notice error">{{ field.schema.title || field.name }}：{{ field.error }}</p>
      <template v-else>
        <label :for="`${prefix}-${field.name}`" class="field-title" :class="{ 'sr-only': overrides }">{{ field.schema.title || field.name }}</label>
        <select v-if="field.schema.enum || (field.schema.type === 'boolean' && field.schema.nullable)" :id="`${prefix}-${field.name}`"
          :value="value(field.name, field.schema)" :disabled="overrides && !owns(field.name)" @change="update(field.name, text($event))">
          <option v-for="choice in choices(field.schema)" :key="JSON.stringify(choice)" :value="JSON.stringify(choice)">{{ choice === null ? '不设置' : String(choice) }}</option>
        </select>
        <label v-else-if="field.schema.type === 'boolean'" class="check-line">
          <input :id="`${prefix}-${field.name}`" type="checkbox" :checked="value(field.name, field.schema) === true"
            :disabled="overrides && !owns(field.name)" @change="update(field.name, checked($event))">{{ value(field.name, field.schema) ? '开启' : '关闭' }}
        </label>
        <textarea v-else-if="field.schema.type === 'array'" :id="`${prefix}-${field.name}`" rows="2" placeholder="每行一个值"
          :value="value(field.name, field.schema) as string" :disabled="overrides && !owns(field.name)" @input="update(field.name, text($event))" />
        <input v-else :id="`${prefix}-${field.name}`" :type="field.schema.type === 'string' ? 'text' : 'number'"
          :value="value(field.name, field.schema) as string" :disabled="overrides && !owns(field.name)"
          :step="field.schema.type === 'integer' ? '1' : 'any'" :min="field.schema.minimum" :max="field.schema.maximum"
          :minlength="field.schema.minLength" :maxlength="field.schema.maxLength" :pattern="field.schema.pattern"
          :required="!field.schema.nullable && ((field.schema.minLength || 0) > 0 || schema.required?.includes(field.name))"
          @input="update(field.name, text($event))">
        <span v-if="overrides && !owns(field.name)" class="hint">继承公共参数</span>
        <span v-else-if="field.schema.description" class="hint">{{ field.schema.description }}</span>
      </template>
    </div>
  </div>
</template>
