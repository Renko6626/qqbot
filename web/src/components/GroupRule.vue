<script setup lang="ts">
import OptionFields from './OptionFields.vue'
import type { GroupDraft, OptionDraft, Schema } from '../types'
defineProps<{ group: GroupDraft; schema: Schema; inherited: OptionDraft }>()
defineEmits<{ remove: [] }>()
</script>

<template>
  <div class="group-rule">
    <div class="group-row">
      <label class="field">群号<input v-model="group.id" inputmode="numeric" pattern="[1-9][0-9]{0,19}" required placeholder="填写群号"></label>
      <label class="field">成员范围<select v-model="group.memberMode"><option value="all">全群成员</option><option value="allowlist">指定成员</option></select></label>
      <button type="button" class="text-button danger" @click="$emit('remove')">移除</button>
    </div>
    <label v-if="group.memberMode === 'allowlist'" class="field group-users">允许的 QQ 号<textarea v-model="group.users" rows="2" placeholder="每行一个 QQ 号；留空不允许任何成员" spellcheck="false" /></label>
    <details v-if="Object.keys(schema.properties || {}).length" class="group-options">
      <summary>本群参数 <span class="muted">{{ Object.keys(group.options).length ? `${Object.keys(group.options).length} 项覆盖` : '全部继承' }}</span></summary>
      <OptionFields v-model="group.options" :schema="schema" :inherited="inherited" overrides />
    </details>
  </div>
</template>
