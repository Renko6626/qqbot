<script setup lang="ts">
import { ref, watch } from 'vue'
import { request, writeHeaders, errorText } from '../api'
import { readSettings, settingsToDraft } from '../schema'
import type { Plugin } from '../types'
import OptionFields from './OptionFields.vue'
import GroupRule from './GroupRule.vue'

const props = defineProps<{ plugin: Plugin; dirty: boolean }>()
const emit = defineEmits<{ dirty: [id: string]; saved: [plugin: Plugin] }>()
const draft = ref(settingsToDraft(props.plugin.settings, props.plugin.options_schema))
let groupKey = draft.value.groups.length
const saving = ref(false)
const message = ref('')
const failed = ref(false)
watch(() => props.plugin, plugin => {
  draft.value = settingsToDraft(plugin.settings, plugin.options_schema)
  groupKey = draft.value.groups.length
})
function changed() { emit('dirty', props.plugin.id); message.value = '' }
function addGroup() {
  draft.value.groups.push({ key: groupKey++, id: '', memberMode: 'all', users: '', options: {}, original: {} })
  changed()
}
async function save() {
  if (saving.value) return
  saving.value = true; failed.value = false; message.value = '正在保存…'
  try {
    const settings = readSettings(draft.value, props.plugin.options_schema, props.plugin.settings)
    const plugin = await request<Plugin>(`/api/plugins/${encodeURIComponent(props.plugin.id)}`, {
      method: 'PUT', headers: { ...writeHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify(settings),
    })
    emit('saved', plugin)
    message.value = plugin.restart_required ? '已保存，加载配置需重启后生效。' : '已保存。'
  } catch (error) { failed.value = true; message.value = errorText(error) }
  finally { saving.value = false }
}
</script>

<template>
  <section class="panel plugin-panel" :id="`plugin-${plugin.id}`" :aria-label="plugin.name">
    <div class="panel-heading">
      <div><h1>{{ plugin.name }}</h1><p class="description">{{ plugin.description }}</p><p v-if="plugin.commands.length" class="commands">{{ plugin.commands.join('　') }}</p></div>
      <span class="badge" :class="{ success: plugin.loaded && plugin.settings.enabled, error: plugin.load_state === 'failed' }">{{ plugin.load_state === 'failed' ? '加载失败' : !plugin.loaded ? '未加载' : plugin.settings.enabled ? '已开启' : '已关闭' }}</span>
    </div>
    <p v-if="plugin.load_error" class="notice error">{{ plugin.load_error }}</p>
    <p v-if="plugin.restart_required" class="notice">{{ plugin.settings.load_on_start ? '待重启后加载' : '待重启后停止加载' }}</p>
    <form @submit.prevent="save" @input="changed" @change="changed">
      <fieldset :disabled="saving">
        <div class="switches"><label class="check-line"><input v-model="draft.enabled" type="checkbox" role="switch">启用功能</label><label class="check-line"><input v-model="draft.load_on_start" type="checkbox">启动时加载</label></div>
        <section v-if="Object.keys(plugin.options_schema.properties || {}).length" class="form-section">
          <div class="section-heading"><h2>公共参数</h2><span class="hint">群内未覆盖的字段继承这里的设置</span></div>
          <OptionFields v-model="draft.options" :schema="plugin.options_schema" />
        </section>
        <section class="form-section">
          <div class="section-heading"><h2>群聊权限</h2><button type="button" class="secondary small" @click="addGroup">添加群</button></div>
          <p v-if="!draft.groups.length" class="empty-inline">尚未添加允许使用的群。</p>
          <GroupRule v-for="(group, index) in draft.groups" :key="group.key" :group="group" :schema="plugin.options_schema" :inherited="draft.options"
            @remove="draft.groups.splice(index, 1); changed()" />
        </section>
        <details class="form-section private-section">
          <summary>私聊权限 <span class="muted">{{ draft.privateMode === 'off' ? '已关闭' : draft.privateMode === 'all' ? '允许所有用户' : '指定用户' }}</span></summary>
          <div class="option-grid">
            <label class="field">用户范围<select v-model="draft.privateMode"><option value="off">关闭私聊</option><option value="all">允许所有私聊用户</option><option value="allowlist">仅指定用户</option></select></label>
            <label v-if="draft.privateMode === 'allowlist'" class="field">允许的 QQ 号<textarea v-model="draft.privateUsers" rows="2" placeholder="留空不允许任何用户" /></label>
          </div>
        </details>
      </fieldset>
      <footer class="form-footer"><p role="status" :class="{ error: failed }">{{ message || (dirty ? '有未保存的修改' : '') }}</p><button type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存配置' }}</button></footer>
    </form>
  </section>
</template>
