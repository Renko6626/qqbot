<script setup lang="ts">
import { ref, watch } from 'vue'
import { request, errorText } from '../api'
import type { Plugin } from '../types'
const props = defineProps<{ plugins: Plugin[] }>()
const pluginId = ref(''), groupId = ref(''), userId = ref(''), message = ref(''), allowed = ref(false)
watch(() => props.plugins, plugins => { if (!plugins.some(item => item.id === pluginId.value)) pluginId.value = plugins[0]?.id || '' }, { immediate: true })
async function preview() {
  try {
    const params = new URLSearchParams({ user_id: userId.value.trim() })
    if (groupId.value.trim()) params.set('group_id', groupId.value.trim())
    const decision = await request<{ allowed: boolean; reason: string }>(`/api/plugins/${encodeURIComponent(pluginId.value)}/permission?${params}`)
    allowed.value = decision.allowed; message.value = `${decision.allowed ? '允许' : '拒绝'}：${decision.reason}`
  } catch (error) { allowed.value = false; message.value = errorText(error) }
}
</script>
<template>
  <details class="panel permission-panel"><summary>权限预览 <span class="hint">按已保存配置判断</span></summary>
    <form class="permission-form" @submit.prevent="preview">
      <label class="field">插件<select v-model="pluginId" required><option v-for="plugin in plugins" :key="plugin.id" :value="plugin.id">{{ plugin.name }}</option></select></label>
      <label class="field">群号<input v-model="groupId" inputmode="numeric" pattern="[1-9][0-9]{0,19}" placeholder="留空表示私聊"></label>
      <label class="field">QQ 号<input v-model="userId" inputmode="numeric" pattern="[1-9][0-9]{0,19}" required></label>
      <button type="submit" class="secondary">检查权限</button>
      <p v-if="message" class="permission-result" :class="allowed ? 'success-text' : 'error'" role="status">{{ message }}</p>
    </form>
  </details>
</template>
