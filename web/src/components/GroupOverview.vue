<script setup lang="ts">
import { computed } from 'vue'
import type { Plugin } from '../types'
const props = defineProps<{ plugins: Plugin[] }>()
defineEmits<{ select: [id: string] }>()
const groups = computed(() => [...new Set(props.plugins.flatMap(plugin => plugin.settings.group_ids))])
function scope(plugin: Plugin, group: string) {
  const users = plugin.settings.group_user_ids[group]
  return users === undefined ? '全群成员' : users.length ? `指定 ${users.length} 位成员` : '成员白名单为空'
}
</script>
<template>
  <section class="panel"><div class="panel-heading"><h1>按群查看</h1><span class="muted">{{ groups.length }} 个群</span></div>
    <p v-if="!groups.length" class="empty-inline">尚未配置群，请先在插件中添加允许使用的群。</p>
    <div v-for="group in groups" :key="group" class="group-summary">
      <h2>群 {{ group }}</h2>
      <div v-for="plugin in plugins.filter(item => item.settings.group_ids.includes(group))" :key="plugin.id" class="summary-row">
        <div><strong>{{ plugin.name }}</strong><p class="hint">{{ plugin.loaded && plugin.settings.enabled ? '已开启' : '当前不可用' }}，{{ scope(plugin, group) }}，{{ Object.keys(plugin.settings.group_options[group] || {}).length || '无' }} 项参数覆盖</p></div>
        <button class="secondary small" @click="$emit('select', plugin.id)">编辑</button>
      </div>
    </div>
  </section>
</template>
