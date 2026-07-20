<template>
  <main class="model-page">
    <header class="page-heading">
      <div>
        <h1>模型管理</h1>
        <p>上传 Food 模型包，通过 Hash、类别契约和冒烟推理校验后再切换线上模型。</p>
      </div>
      <el-button :icon="RefreshLeft" :disabled="!canRollback" :loading="rollbackLoading" @click="rollback">
        {{ rollbackLoading ? '回滚中' : '回滚上一版本' }}
      </el-button>
    </header>

    <section class="active-model" aria-labelledby="active-model-title">
      <div>
        <span class="section-label">当前识别模型</span>
        <h2 id="active-model-title">{{ activeModel?.name || '尚未启用注册模型' }}</h2>
        <p v-if="activeModel">
          {{ activeModel.version }} · {{ taskText(activeModel.task) }} · {{ activeModel.class_count }} 个类别
        </p>
        <p v-else>系统仍可使用本地环境配置的模型；上传模型不会自动切换。</p>
      </div>
      <el-tag :type="activeModel ? 'success' : 'info'" effect="light">
        {{ activeModel ? '运行正常' : '等待启用' }}
      </el-tag>
    </section>

    <section class="upload-panel" aria-labelledby="upload-title">
      <div class="upload-copy">
        <h2 id="upload-title">上传模型包</h2>
        <p>ZIP 根目录须包含 best.pt、classes.yaml 和 manifest.json，最大 512 MiB。</p>
      </div>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".zip,application/zip"
        :on-change="selectPackage"
        :on-remove="clearPackage"
      >
        <el-button :icon="Upload">选择 ZIP</el-button>
      </el-upload>
      <el-button
        type="primary"
        :icon="CircleCheck"
        :disabled="!selectedPackage"
        :loading="uploading"
        @click="upload"
      >
        {{ uploading ? (uploadProgress >= 100 ? '正在校验' : '上传中') : '上传并校验' }}
      </el-button>
      <el-progress v-if="uploading" :percentage="uploadProgress" :stroke-width="8" />
    </section>

    <section class="model-list" v-loading="loading" aria-labelledby="model-list-title">
      <div class="list-heading">
        <h2 id="model-list-title">已上传版本</h2>
        <el-button text :icon="Refresh" @click="loadModels">刷新</el-button>
      </div>

      <el-empty v-if="!loading && models.length === 0" description="还没有上传模型包" />
      <el-table v-else :data="models" row-key="model_id">
        <el-table-column label="模型" min-width="190">
          <template #default="{ row }">
            <strong>{{ row.name }}</strong>
            <div class="cell-subtitle">{{ row.version }}</div>
          </template>
        </el-table-column>
        <el-table-column label="任务" width="130">
          <template #default="{ row }">
            <el-tag :type="row.task === 'detect' ? 'success' : 'warning'" effect="plain">
              {{ taskText(row.task) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="class_count" label="类别数" width="90" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row)" effect="light">{{ statusText(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权重 Hash" min-width="150">
          <template #default="{ row }"><code>{{ shortHash(row.weight_sha256) }}</code></template>
        </el-table-column>
        <el-table-column label="上传时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="!row.is_active && row.status === 'ready'"
              link
              type="success"
              :loading="activatingId === row.model_id"
              :disabled="Boolean(activatingId || deletingId || rollbackLoading)"
              @click="activate(row)"
            >{{ activatingId === row.model_id ? '启用中' : '启用' }}</el-button>
            <el-button
              v-if="!row.is_active"
              link
              type="danger"
              :loading="deletingId === row.model_id"
              :disabled="Boolean(activatingId || deletingId || rollbackLoading)"
              @click="remove(row)"
            >{{ deletingId === row.model_id ? '删除中' : '删除' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="detailVisible" title="模型详情" size="min(560px, 92vw)">
      <template v-if="selectedModel">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="名称">{{ selectedModel.name }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ selectedModel.version }}</el-descriptions-item>
          <el-descriptions-item label="任务">{{ taskText(selectedModel.task) }}</el-descriptions-item>
          <el-descriptions-item label="类别数">{{ selectedModel.class_count }}</el-descriptions-item>
          <el-descriptions-item label="权重 Hash"><code>{{ selectedModel.weight_sha256 }}</code></el-descriptions-item>
          <el-descriptions-item label="类别表 Hash"><code>{{ selectedModel.classes_sha256 }}</code></el-descriptions-item>
          <el-descriptions-item label="校验结果">
            {{ selectedModel.validation_error || '校验通过' }}
          </el-descriptions-item>
        </el-descriptions>

        <section class="detail-section">
          <h3>类别</h3>
          <div class="class-list">
            <el-tag v-for="item in selectedModel.classes" :key="item.class_id" effect="plain">
              {{ item.display_name }}
            </el-tag>
          </div>
        </section>

        <section class="detail-section">
          <h3>训练材料</h3>
          <pre v-if="hasTrainingDetails">{{ trainingDetails }}</pre>
          <el-empty v-else description="训练方尚未提供真实数据集统计或指标" :image-size="72" />
        </section>
      </template>
    </el-drawer>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { CircleCheck, Refresh, RefreshLeft, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  activateFoodModel,
  deleteFoodModel,
  getFoodModels,
  rollbackFoodModel,
  uploadFoodModel,
} from '@/api/foodModel'
import { formatTime } from '@/utils/format'

const models = ref([])
const activeModelId = ref(null)
const loading = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const activatingId = ref(null)
const deletingId = ref(null)
const rollbackLoading = ref(false)
const uploadRef = ref(null)
const selectedPackage = ref(null)
const detailVisible = ref(false)
const selectedModel = ref(null)

const activeModel = computed(() => models.value.find((item) => item.model_id === activeModelId.value) || null)
const canRollback = computed(() => models.value.filter((item) => item.available).length > 1 && Boolean(activeModel.value))
const hasTrainingDetails = computed(() => Boolean(selectedModel.value?.dataset || selectedModel.value?.metrics))
const trainingDetails = computed(() => JSON.stringify({
  dataset: selectedModel.value?.dataset || null,
  metrics: selectedModel.value?.metrics || null,
}, null, 2))

async function loadModels() {
  loading.value = true
  try {
    const response = await getFoodModels()
    models.value = response.data?.items || []
    activeModelId.value = response.data?.active_model_id || null
  } finally {
    loading.value = false
  }
}

function selectPackage(file) {
  selectedPackage.value = file.raw || null
}

function clearPackage() {
  selectedPackage.value = null
}

async function upload() {
  if (!selectedPackage.value || uploading.value) return
  uploading.value = true
  uploadProgress.value = 0
  try {
    await uploadFoodModel(selectedPackage.value, (event) => {
      if (event.total) uploadProgress.value = Math.round((event.loaded / event.total) * 100)
    })
    ElMessage.success('模型包校验通过，可以手动启用了')
    selectedPackage.value = null
    uploadRef.value?.clearFiles()
    await loadModels()
  } finally {
    uploading.value = false
  }
}

async function activate(row) {
  await ElMessageBox.confirm(
    `启用 ${row.name} ${row.version}？系统会先执行冒烟推理，失败时继续使用当前模型。`,
    '确认切换模型',
    { confirmButtonText: '启用', cancelButtonText: '取消', type: 'warning' },
  )
  activatingId.value = row.model_id
  try {
    await activateFoodModel(row.model_id)
    ElMessage.success('模型已安全切换')
    await loadModels()
  } finally {
    activatingId.value = null
  }
}

async function rollback() {
  await ElMessageBox.confirm('回滚到上一健康模型？', '确认回滚', {
    confirmButtonText: '回滚', cancelButtonText: '取消', type: 'warning',
  })
  rollbackLoading.value = true
  try {
    await rollbackFoodModel()
    ElMessage.success('已回滚到上一健康模型')
    await loadModels()
  } finally {
    rollbackLoading.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `永久删除 ${row.name} ${row.version} 的受控模型文件？`,
    '删除模型',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'error' },
  )
  deletingId.value = row.model_id
  try {
    await deleteFoodModel(row.model_id)
    ElMessage.success('模型已删除')
    await loadModels()
  } finally {
    deletingId.value = null
  }
}

function openDetail(row) {
  selectedModel.value = row
  detailVisible.value = true
}

function taskText(task) {
  return task === 'classify' ? '整图分类' : '目标检测'
}

function statusText(row) {
  if (row.is_active) return '已启用'
  return { validating: '校验中', ready: '可用', failed: '校验失败' }[row.status] || row.status
}

function statusType(row) {
  if (row.is_active) return 'success'
  return { validating: 'warning', ready: 'primary', failed: 'danger' }[row.status] || 'info'
}

function shortHash(value = '') {
  return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : '-'
}

onMounted(loadModels)
</script>

<style scoped>
.model-page { display: grid; gap: 20px; min-height: 100%; padding: 24px; background: #f8f7f3; color: #352a21; }
.page-heading, .active-model, .upload-panel, .list-heading { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.page-heading h1, .active-model h2, .upload-panel h2, .list-heading h2 { margin: 0; }
.page-heading p, .active-model p, .upload-panel p { margin: 6px 0 0; color: #75685d; }
.active-model, .upload-panel, .model-list { padding: 20px; border: 1px solid #e5dfd7; border-radius: 8px; background: #fff; }
.active-model { border-left: 4px solid #78913b; }
.section-label { color: #78913b; font-size: 13px; font-weight: 700; }
.upload-panel { display: grid; grid-template-columns: minmax(240px, 1fr) auto auto; }
.upload-panel :deep(.el-progress) { grid-column: 1 / -1; }
.list-heading { margin-bottom: 14px; }
.cell-subtitle { margin-top: 4px; color: #87796c; font-size: 12px; }
code { overflow-wrap: anywhere; color: #655141; }
.detail-section { margin-top: 24px; }
.detail-section h3 { margin-bottom: 12px; }
.class-list { display: flex; flex-wrap: wrap; gap: 8px; }
pre { overflow: auto; padding: 14px; border-radius: 6px; background: #f7f5f1; white-space: pre-wrap; }
@media (max-width: 760px) {
  .model-page { padding: 14px; }
  .page-heading, .active-model { align-items: flex-start; flex-direction: column; }
  .upload-panel { grid-template-columns: 1fr; }
}
</style>
