<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorText, formatDate, request, writeHeaders } from '../api'
import type { AlbumImage } from '../types'

const albums = ref<{ id: string }[]>([]), selected = ref(''), images = ref<AlbumImage[]>([])
const busy = ref(false), message = ref(''), failed = ref(false), creating = ref(false), newId = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const uploadReady = ref(false)
const albumPath = computed(() => `/api/albums/${encodeURIComponent(selected.value)}`)
async function action(work: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; failed.value = false; message.value = ''
  try { await work() } catch (error) { failed.value = true; message.value = errorText(error) }
  finally { busy.value = false }
}
function resetUpload() { if (fileInput.value) fileInput.value.value = ''; uploadReady.value = false }
async function loadImages() {
  images.value = []
  if (selected.value) {
    const list = await request<AlbumImage[]>(`${albumPath.value}/images`)
    images.value = list.sort((a, b) => b.created_at.localeCompare(a.created_at))
  }
}
async function loadAlbums(preferred = selected.value) {
  const list = await request<{ id: string }[]>('/api/albums')
  albums.value = list
  selected.value = list.some(album => album.id === preferred) ? preferred : list[0]?.id || ''
  resetUpload()
  await loadImages()
}
function refresh() { return action(() => loadAlbums()) }
function selectAlbum() { resetUpload(); return action(loadImages) }
function createAlbum() {
  return action(async () => {
    const id = newId.value.trim()
    await request('/api/albums', { method: 'POST', headers: { ...writeHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) })
    await loadAlbums(id); newId.value = ''; creating.value = false; message.value = `已打开图集“${id}”。`
  })
}
function upload() {
  const file = fileInput.value?.files?.[0]
  if (!file || !selected.value) return
  if (file.size > 10 * 1024 * 1024) { failed.value = true; message.value = '图片不能超过 10 MiB。'; return }
  return action(async () => {
    await request(`${albumPath.value}/images`, { method: 'POST', headers: { ...writeHeaders, 'Content-Type': file.type || 'application/octet-stream' }, body: file })
    resetUpload(); await loadImages(); message.value = '图片已上传。'
  })
}
function deleteImage(image: AlbumImage) {
  if (!confirm(`确认从图集“${image.album}”删除这张图片？删除后无法恢复，晚安插件也不会再抽到它。`)) return
  return action(async () => {
    await request(image.url, { method: 'DELETE', headers: writeHeaders })
    await loadImages(); message.value = '图片已删除。'
  })
}
function deleteAlbum() {
  if (!selected.value || !confirm(`确认删除空图集“${selected.value}”？此操作不会修改插件中的图集配置。`)) return
  return action(async () => {
    await request(albumPath.value, { method: 'DELETE', headers: writeHeaders })
    await loadAlbums(); message.value = '空图集已删除。'
  })
}
function source(image: AlbumImage) {
  return image.source === 'upload' ? '手动上传' : image.source === 'anime_rating_watch' ? '图片监测' : image.source
}
onMounted(refresh)
</script>

<template>
  <section class="panel album-panel" :aria-busy="busy">
    <div class="panel-heading"><div><h1>图集管理</h1><p class="description">查看上传与插件保存的图片，维护随机取图范围。</p></div><span class="badge">{{ albums.length }} 个图集</span></div>
    <fieldset :disabled="busy">
      <div class="album-toolbar">
        <label class="album-picker"><span class="sr-only">当前图集</span><select v-model="selected" :disabled="!albums.length" @change="selectAlbum"><option v-if="!albums.length" value="">暂无图集</option><option v-for="album in albums" :key="album.id" :value="album.id">{{ album.id }}</option></select></label>
        <span class="hint image-count">{{ selected ? `${images.length} 张图片` : '' }}</span>
        <button class="secondary small" type="button" @click="refresh">刷新</button>
        <button class="secondary small" type="button" :aria-expanded="creating" @click="creating = !creating">新建图集</button>
        <button class="text-button danger" type="button" :disabled="!selected || images.length > 0" @click="deleteAlbum">删除空图集</button>
      </div>
      <form v-if="creating" class="album-create" @submit.prevent="createAlbum"><label class="field">图集 ID<input v-model="newId" pattern="[A-Za-z0-9_-]{1,64}" maxlength="64" required placeholder="例如 goodnight"><span class="hint">使用英文字母、数字、下划线或短横线。</span></label><button class="secondary" type="submit">创建</button></form>
      <form v-if="selected" class="upload-bar" @submit.prevent="upload">
        <label class="upload-file"><span class="sr-only">选择上传图片</span><input ref="fileInput" type="file" accept="image/jpeg,image/png,image/gif,image/webp,image/bmp,image/tiff,image/avif" required @change="uploadReady = !!fileInput?.files?.length"></label>
        <button type="submit" :disabled="!uploadReady">上传图片</button><span class="hint">单张最多 10 MiB</span>
      </form>
    </fieldset>
    <p v-if="busy || message" class="operation-status" :class="{ error: failed }" role="status">{{ message || '正在处理…' }}</p>
    <p class="album-help hint">插件中填写图集 ID 即可使用；删除图片后不再参与随机取图。</p>
    <div v-if="images.length" class="album-grid" :inert="busy">
      <article v-for="image in images" :key="image.id" class="album-image">
        <a :href="image.url" target="_blank" rel="noopener" :aria-label="`查看原图 ${image.id}`"><img :src="image.url" :alt="`图集图片 ${image.id}`" loading="lazy" decoding="async"></a>
        <div class="image-body"><p class="image-source">{{ source(image) }}<span v-if="image.metadata?.group_id">，群 {{ image.metadata.group_id }}</span></p><time :datetime="image.created_at">{{ formatDate(image.created_at) }}</time><p class="image-id" :title="image.id">{{ image.id }}</p>
          <div class="image-actions"><a :href="image.url" target="_blank" rel="noopener">查看原图</a><button type="button" class="text-button danger" :aria-label="`删除图片 ${image.id}`" @click="deleteImage(image)">删除</button></div>
        </div>
      </article>
    </div>
    <p v-else-if="!busy" class="empty-state">{{ selected ? '图集还是空的，可以上传图片，也可以让图片监测插件写入。' : '还没有图集。新建图集后即可上传图片。' }}</p>
  </section>
</template>
