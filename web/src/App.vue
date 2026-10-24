<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { errorText, formatDate, request, writeHeaders } from './api'
import type { Plugin, Status } from './types'
import PluginEditor from './components/PluginEditor.vue'
import GroupOverview from './components/GroupOverview.vue'
import PermissionPreview from './components/PermissionPreview.vue'
import AlbumManager from './components/AlbumManager.vue'

type View = 'plugins' | 'groups' | 'albums'
const initialView = location.hash.slice(1)
const view = ref<View>(initialView === 'albums' || initialView === 'groups' ? initialView : 'plugins')
const plugins = ref<Plugin[]>([]), selected = ref(''), status = ref<Status | null>(null)
const dirty = reactive(new Set<string>())
const loading = ref(false), restarting = ref(false), error = ref(''), processMessage = ref(''), processFailed = ref(false), checkedAt = ref('')
const views: { id: View; label: string }[] = [{ id: 'plugins', label: '插件设置' }, { id: 'groups', label: '按群查看' }, { id: 'albums', label: '图集管理' }]
const connected = computed(() => (status.value?.connected_accounts.length || 0) > 0)
const pending = computed(() => plugins.value.some(plugin => plugin.restart_required))
const coolify = computed(() => {
  try { const url = new URL(status.value?.coolify_url || ''); return url.protocol === 'https:' ? url.href : '' } catch { return '' }
})
function show(next: View) { view.value = next; history.replaceState(null, '', `#${next}`) }
function selectPlugin(id: string) { selected.value = id; show('plugins') }
function pluginState(plugin: Plugin) {
  return plugin.load_state === 'failed' ? '加载失败' : !plugin.loaded ? '未加载' : plugin.settings.enabled ? '已开启' : '已关闭'
}
function saved(plugin: Plugin) {
  const index = plugins.value.findIndex(item => item.id === plugin.id)
  if (index !== -1) plugins.value[index] = plugin
  dirty.delete(plugin.id)
}
async function refresh() {
  if (loading.value) return
  loading.value = true; error.value = ''
  try {
    const [nextStatus, list] = await Promise.all([request<Status>('/api/status'), request<Plugin[]>('/api/plugins')])
    status.value = nextStatus; plugins.value = list; dirty.clear(); checkedAt.value = new Date().toISOString()
    if (!list.some(plugin => plugin.id === selected.value)) selected.value = list[0]?.id || ''
  } catch (cause) { error.value = errorText(cause) }
  finally { loading.value = false }
}
function manualRefresh() {
  if (!dirty.size || confirm('有未保存的修改，刷新会丢弃这些修改。继续刷新？')) return refresh()
}
async function restart() {
  processFailed.value = false
  if (dirty.size) { processMessage.value = '请先保存配置；有未保存的修改，尚未执行重启。'; return }
  if (!confirm('重启 NoneBot 会短暂断开 QQ 连接，随后自动恢复。确认重启进程？')) return
  restarting.value = true; processMessage.value = '正在请求重启…'
  try {
    const previous = await request<{ started_at: string }>('/api/restart', { method: 'POST', headers: writeHeaders })
    processMessage.value = '重启请求已接受，等待进程恢复…'
    const deadline = Date.now() + 30_000
    let restored = false
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 1500))
      try {
        const current = await request<Status>('/api/status', { signal: AbortSignal.timeout(2000) })
        if (current.started_at !== previous.started_at) { restored = true; break }
      } catch { /* Docker may still be starting. */ }
    }
    if (restored) { processMessage.value = '进程已重启，QQ 连接可能仍在恢复。'; await refresh() }
    else { processFailed.value = true; processMessage.value = '尚未确认进程恢复，请刷新状态或到 Coolify 查看日志。' }
  } catch (cause) { processFailed.value = true; processMessage.value = errorText(cause) }
  finally { restarting.value = false }
}
onMounted(refresh)
</script>

<template>
  <header class="topbar">
    <a href="/" class="brand"><span class="brand-mark" aria-hidden="true">Q</span>QQ Bot <span class="brand-label">管理</span></a>
    <div class="header-actions">
      <span class="connection-state" :class="{ connected }"><i aria-hidden="true" />{{ status ? connected ? 'QQ 已连接' : 'QQ 未连接' : '正在连接…' }}</span>
      <button class="secondary small" :disabled="loading || restarting" @click="manualRefresh">{{ loading ? '刷新中…' : '刷新状态' }}</button>
      <details class="process-menu"><summary>进程</summary><div class="process-popover">
        <dl><dt>QQ 账号</dt><dd>{{ status?.connected_accounts.join('、') || '尚未连接，请检查 SnowLuma 登录状态' }}</dd><dt>进程启动</dt><dd>{{ status ? formatDate(status.started_at) : '—' }}</dd><dt>最近检查</dt><dd>{{ checkedAt ? formatDate(checkedAt) : '—' }}</dd></dl>
        <button class="secondary small" :disabled="!status?.process_restart_supported || restarting" @click="restart">{{ restarting ? '正在重启…' : '重启 NoneBot 进程' }}</button>
        <p class="hint">重启读取已保存配置，不更新源码或依赖。</p>
        <a v-if="coolify" :href="coolify" target="_blank" rel="noopener">在 Coolify 管理进程</a>
        <a href="https://snowluma.secret-sealing.club/" target="_blank" rel="noopener">打开 SnowLuma</a>
      </div></details>
    </div>
  </header>
  <main class="app-layout">
    <aside class="sidebar" :inert="restarting">
      <div class="directory-heading"><h2>插件目录</h2><span>{{ plugins.length }}</span></div>
      <nav aria-label="插件目录">
        <button v-for="plugin in plugins" :key="plugin.id" class="directory-entry" :aria-current="view === 'plugins' && selected === plugin.id ? 'true' : undefined" @click="selectPlugin(plugin.id)">
          <span class="directory-name">{{ plugin.name }}</span><span class="directory-meta"><i :class="{ active: plugin.loaded && plugin.settings.enabled, failed: plugin.load_state === 'failed' }" />{{ pluginState(plugin) }}<span v-if="dirty.has(plugin.id)" class="dirty-mark">未保存</span><span v-if="plugin.restart_required" class="dirty-mark">待重启</span></span>
        </button>
      </nav>
      <details class="config-notes"><summary>配置如何生效</summary><p>开关、群范围和参数保存后供下一次处理使用。启动加载变更需重启进程。</p><p>群参数未单独设置时继承公共值；指定成员列表为空表示无人可用。</p></details>
    </aside>
    <div class="content-area" :inert="restarting">
      <div class="section-nav"><nav aria-label="管理区域"><button v-for="item in views" :key="item.id" :aria-pressed="view === item.id" @click="show(item.id)">{{ item.label }}</button></nav><span v-if="dirty.size" class="hint draft-count">{{ dirty.size }} 个插件未保存</span></div>
      <p v-if="error" class="notice error" role="alert">{{ error }}</p>
      <p v-if="processMessage" class="notice" :class="{ error: processFailed }" role="status">{{ processMessage }}</p>
      <p v-if="pending" class="notice">加载配置有变更，重启 NoneBot 后生效。</p>
      <label v-show="view === 'plugins' && plugins.length" class="mobile-plugin-select field"><span class="sr-only">选择插件</span><select v-model="selected"><option v-for="plugin in plugins" :key="plugin.id" :value="plugin.id">{{ plugin.name }}{{ dirty.has(plugin.id) ? '（未保存）' : '' }}</option></select></label>
      <div v-show="view === 'plugins'" id="plugins">
        <PluginEditor v-for="plugin in plugins" v-show="selected === plugin.id" :key="plugin.id" :plugin="plugin" :dirty="dirty.has(plugin.id)" @dirty="dirty.add($event)" @saved="saved" />
        <p v-if="!plugins.length" class="panel empty-state">{{ loading ? '正在加载插件…' : '暂无可配置的插件。' }}</p>
      </div>
      <GroupOverview v-show="view === 'groups'" :plugins="plugins" @select="selectPlugin" />
      <AlbumManager v-if="view === 'albums'" />
      <PermissionPreview v-show="view !== 'albums'" :plugins="plugins" />
    </div>
  </main>
</template>
