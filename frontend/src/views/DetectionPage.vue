<template>
  <div class="detection-page">
    <!-- 左侧控制面板 -->
    <div class="control-panel">
      <h3>检测控制台</h3>
      
      <!-- 场景选择 -->
      <div class="control-section">
        <label>检测场景</label>
        <el-select v-model="selectedScene" placeholder="选择检测场景" @change="onSceneChange">
          <el-option
            v-for="scene in scenes"
            :key="scene.id"
            :label="scene.display_name"
            :value="scene.id"
          >
            <span>{{ scene.display_name }}</span>
            <span class="scene-category">{{ scene.category }}</span>
          </el-option>
        </el-select>
      </div>

      <!-- 检测模型选择 -->
      <div class="control-section">
        <label>检测模型</label>
        <el-select v-model="selectedModelId" placeholder="请选择检测模型">
          <el-option
            v-for="m in sceneModels"
            :key="m.model_id"
            :label="`${m.model_name}${m.is_default ? ' (默认)' : ''}`"
            :value="m.model_id"
          />
        </el-select>
      </div>

      <!-- 检测模式 -->
      <div class="control-section">
        <label>检测模式</label>
        <el-radio-group v-model="detectMode">
          <el-radio-button value="single">单图检测</el-radio-button>
          <el-radio-button value="batch">批量检测</el-radio-button>
          <el-radio-button value="video">视频检测</el-radio-button>
          <el-radio-button value="camera">实时摄像头</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 参数设置 -->
      <div class="control-section">
        <label>置信度阈值</label>
        <el-slider v-model="confThreshold" :min="0.1" :max="1" :step="0.05" show-input />
      </div>

      <div class="control-section">
        <label>IoU 阈值</label>
        <el-slider v-model="iouThreshold" :min="0.1" :max="1" :step="0.05" show-input />
      </div>

      <!-- 文件上传 -->
      <div class="control-section" v-if="detectMode !== 'camera'">
        <label>上传{{ detectMode === 'video' ? '视频' : '图像' }}</label>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :multiple="detectMode === 'batch'"
          :accept="detectMode === 'video' ? 'video/*' : 'image/*'"
          :on-change="handleFileChange"
          :file-list="fileList"
          drag
        >
          <el-icon :size="48"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            拖拽文件到此处，或<em>点击上传</em>
          </div>
        </el-upload>
      </div>

      <!-- 检测按钮 -->
      <el-button
        v-if="detectMode !== 'camera'"
        type="primary"
        size="large"
        :loading="detecting"
        :disabled="!selectedScene || !selectedModelId || fileList.length === 0"
        @click="startDetection"
        class="detect-btn"
      >
        <el-icon><Aim /></el-icon>开始检测
      </el-button>
      
      <!-- 摄像头控制按钮 -->
      <el-button
        v-else
        :type="cameraActive ? 'danger' : 'success'"
        size="large"
        @click="toggleCamera"
        :disabled="!selectedScene || !selectedModelId"
        class="detect-btn"
      >
        <el-icon><VideoCamera /></el-icon>
        {{ cameraActive ? '停止检测' : '开启摄像头' }}
      </el-button>
    </div>

    <!-- 右侧结果展示 -->
    <div class="result-panel">
      <!-- 摄像头实时检测 -->
      <div v-if="detectMode === 'camera'" class="camera-container">
        <div class="camera-header">
          <h3>实时摄像头检测</h3>
          <div v-if="cameraActive" class="camera-stats">
            <el-tag type="success">FPS: {{ cameraFps }}</el-tag>
            <el-tag type="info">目标: {{ cameraObjects }}</el-tag>
          </div>
        </div>
        
        <div class="camera-view">
          <!-- 原始视频 -->
          <div class="video-wrapper">
            <h4>原始画面</h4>
            <video ref="videoRef" autoplay muted playsinline class="camera-video"></video>
          </div>
          
          <!-- 检测结果 -->
          <div class="video-wrapper">
            <h4>检测结果</h4>
            <canvas ref="cameraCanvasRef" class="camera-canvas"></canvas>
          </div>
        </div>
        
        <!-- 检测详情 -->
        <div v-if="cameraDetections.length > 0" class="detection-details">
          <h4>实时检测结果</h4>
          <el-table :data="cameraDetections" stripe max-height="200">
            <el-table-column prop="class_name" label="类别" width="120" />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                {{ (row.confidence * 100).toFixed(1) }}%
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      
      <!-- 单图/视频检测结果 -->
      <div v-else-if="detectionResult && detectMode !== 'batch'" class="result-content">
        <div class="result-header">
          <h3>检测结果</h3>
          <div class="result-stats">
            <el-tag type="success">目标数量: {{ detectionResult.total_objects }}</el-tag>
            <el-tag type="info">推理时间: {{ detectionResult.inference_time?.toFixed(2) }}ms</el-tag>
          </div>
        </div>

        <!-- 图像展示 -->
        <div class="image-container" v-if="detectMode !== 'video'">
          <canvas ref="canvasRef" class="detection-canvas"></canvas>
        </div>

        <!-- 视频展示 -->
        <div class="video-container" v-else>
          <video :src="detectionResult.video_url" controls class="detection-video"></video>
        </div>

        <!-- 检测详情 -->
        <div class="detection-details">
          <h4>检测详情</h4>
          <el-table :data="detectionResult.detections" stripe max-height="300">
            <el-table-column prop="class_name" label="类别" width="120" />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                {{ (row.confidence * 100).toFixed(1) }}%
              </template>
            </el-table-column>
            <el-table-column label="位置 (x1, y1, x2, y2)">
              <template #default="{ row }">
                {{ row.bbox.map(v => v.toFixed(0)).join(', ') }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 批量检测结果 -->
      <div v-else-if="detectMode === 'batch' && batchResults.length > 0" class="result-content">
        <div class="result-header">
          <h3>批量检测结果</h3>
          <div class="result-stats">
            <el-tag type="success">图片数量: {{ batchResults.length }}</el-tag>
            <el-tag type="info">总目标数: {{ batchResults.reduce((sum, r) => sum + (r.total_objects || 0), 0) }}</el-tag>
          </div>
        </div>
        <div class="batch-grid">
          <div v-for="(result, idx) in batchResults" :key="idx" class="batch-item">
            <div class="batch-item-header">
              <span class="batch-filename">{{ result.image_name || `图片 ${idx + 1}` }}</span>
              <div class="batch-item-stats">
                <el-tag size="small" type="success">{{ result.total_objects || 0 }} 个目标</el-tag>
                <el-tag size="small" type="info">{{ result.inference_time?.toFixed(1) }}ms</el-tag>
              </div>
            </div>
            <div class="batch-canvas-wrap">
              <canvas :ref="el => batchCanvasRefs[idx] = el" class="detection-canvas"></canvas>
            </div>
            <el-table v-if="result.detections?.length" :data="result.detections" stripe size="small" max-height="160">
              <el-table-column prop="class_name" label="类别" width="100" />
              <el-table-column prop="confidence" label="置信度" width="90">
                <template #default="{ row }">
                  {{ (row.confidence * 100).toFixed(1) }}%
                </template>
              </el-table-column>
              <el-table-column label="位置">
                <template #default="{ row }">
                  {{ row.bbox.map(v => v.toFixed(0)).join(', ') }}
                </template>
              </el-table-column>
            </el-table>
            <div v-else class="batch-no-detection">未检测到目标</div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-result">
        <el-icon :size="64"><Aim /></el-icon>
        <p v-if="detectMode === 'camera'">选择场景并开启摄像头</p>
        <p v-else>上传图像并开始检测</p>
        <p class="hint">支持单图、批量、视频、实时摄像头检测模式</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { UploadFilled, Aim, VideoCamera } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getScenesApi, detectSingleApi, detectBatchApi, detectVideoApi } from '@/api/detection'
import { getSceneModelsApi } from '@/api/model'

// 场景列表
const scenes = ref([])
const selectedScene = ref(null)
const selectedModelId = ref(null)
const sceneModels = ref([])
const detectMode = ref('single')
const confThreshold = ref(0.25)
const iouThreshold = ref(0.45)

// 文件上传
const fileList = ref([])
const uploadRef = ref(null)

// 检测状态
const detecting = ref(false)
const detectionResult = ref(null)
const batchResults = ref([])
const batchCanvasRefs = ref([])
const canvasRef = ref(null)
const currentImage = ref(null)

// 摄像头相关状态
const videoRef = ref(null)
const cameraCanvasRef = ref(null)
const cameraActive = ref(false)
const cameraFps = ref(0)
const cameraObjects = ref(0)
const cameraDetections = ref([])
let ws = null
let animationFrameId = null
let mediaStream = null

// 加载场景列表
async function loadScenes() {
  try {
    const res = await getScenesApi()
    scenes.value = res.data || []
    if (scenes.value.length > 0) {
      selectedScene.value = scenes.value[0].id
    }
  } catch (error) {
    console.error('加载场景失败:', error)
  }
}

// 场景变更
async function onSceneChange() {
  detectionResult.value = null
  fileList.value = []
  selectedModelId.value = null
  // 加载场景关联的已启用模型
  if (selectedScene.value) {
    try {
      const res = await getSceneModelsApi(selectedScene.value)
      sceneModels.value = res.data || []
      // 自动选中场景的默认模型
      const defaultModel = sceneModels.value.find(m => m.is_default)
      if (defaultModel) {
        selectedModelId.value = defaultModel.model_id
      }
    } catch (error) {
      console.error('加载模型列表失败:', error)
      sceneModels.value = []
    }
  } else {
    sceneModels.value = []
  }
}

// 文件变更
function handleFileChange(file, uploadFiles) {
  if (detectMode.value === 'batch') {
    // 批量模式：使用 uploadFiles（el-upload 内部完整文件列表）
    fileList.value = uploadFiles
  } else {
    // 单图/视频模式：只保留当前文件
    fileList.value = [file]
  }
}

// 开始检测
async function startDetection() {
  if (!selectedScene.value || fileList.value.length === 0) {
    ElMessage.warning('请选择场景并上传文件')
    return
  }

  detecting.value = true
  detectionResult.value = null

  try {
    const params = {
      scene_id: selectedScene.value,
      conf_threshold: confThreshold.value,
      iou_threshold: iouThreshold.value
    }
    // 根据选中的模型获取其默认版本ID
    if (selectedModelId.value) {
      const selectedModel = sceneModels.value.find(m => m.model_id === selectedModelId.value)
      if (selectedModel?.default_version_id) {
        params.model_version_id = selectedModel.default_version_id
      }
    }

    let res
    if (detectMode.value === 'single') {
      res = await detectSingleApi({
        ...params,
        image: fileList.value[0].raw
      })
      detectionResult.value = res.data
    } else if (detectMode.value === 'batch') {
      res = await detectBatchApi({
        ...params,
        images: fileList.value.map(f => f.raw)
      })
      // 批量结果：附带文件名便于展示
      batchResults.value = (res.data?.results || []).map((r, i) => ({
        ...r,
        image_name: fileList.value[i]?.name || `图片 ${i + 1}`,
      }))
    } else {
      res = await detectVideoApi({
        ...params,
        video: fileList.value[0].raw
      })
      detectionResult.value = res.data
    }

    ElMessage.success('检测完成')

    // 绘制检测框
    await nextTick()
    if (detectMode.value === 'single') {
      drawDetections()
    } else if (detectMode.value === 'batch') {
      drawBatchDetections()
      // 批量检测完成后清理已上传的文件列表
      fileList.value = []
      uploadRef.value?.clearFiles()
    }
  } catch (error) {
    ElMessage.error('检测失败: ' + (error.message || '未知错误'))
  } finally {
    detecting.value = false
  }
}

// 绘制检测框
function drawDetections() {
  const canvas = canvasRef.value
  if (!canvas || !detectionResult.value) return

  const ctx = canvas.getContext('2d')
  const img = new Image()
  
  // 获取上传的图像
  const file = fileList.value[0]
  if (!file) return

  img.onload = () => {
    // 设置canvas尺寸
    canvas.width = img.width
    canvas.height = img.height
    
    // 绘制图像
    ctx.drawImage(img, 0, 0)
    
    // 释放 Object URL，避免内存泄漏
    URL.revokeObjectURL(img.src)
    
    // 绘制检测框
    const detections = detectionResult.value.detections || []
    detections.forEach(det => {
      const [x1, y1, x2, y2] = det.bbox
      
      // 绘制边界框
      ctx.strokeStyle = '#409eff'
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
      
      // 绘制标签背景
      const label = `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`
      ctx.font = '14px Arial'
      const textWidth = ctx.measureText(label).width
      ctx.fillStyle = '#409eff'
      ctx.fillRect(x1, y1 - 24, textWidth + 10, 24)
      
      // 绘制标签文字
      ctx.fillStyle = '#fff'
      ctx.fillText(label, x1 + 5, y1 - 6)
    })
  }
  
  img.src = URL.createObjectURL(file.raw)
}

// 绘制批量检测框
function drawBatchDetections() {
  if (batchResults.value.length === 0) return

  batchResults.value.forEach((result, idx) => {
    const file = fileList.value[idx]
    if (!file) return

    const canvas = batchCanvasRefs.value[idx]
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    const img = new Image()

    img.onload = () => {
      canvas.width = img.width
      canvas.height = img.height
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(img.src)

      const detections = result.detections || []
      detections.forEach(det => {
        const [x1, y1, x2, y2] = det.bbox
        ctx.strokeStyle = '#409eff'
        ctx.lineWidth = 2
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

        const label = `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`
        ctx.font = '14px Arial'
        const textWidth = ctx.measureText(label).width
        ctx.fillStyle = '#409eff'
        ctx.fillRect(x1, y1 - 24, textWidth + 10, 24)
        ctx.fillStyle = '#fff'
        ctx.fillText(label, x1 + 5, y1 - 6)
      })
    }

    img.src = URL.createObjectURL(file.raw)
  })
}

// 监听检测模式变化
watch(detectMode, () => {
  fileList.value = []
  detectionResult.value = null
  batchResults.value = []
  if (detectMode.value !== 'camera' && cameraActive.value) {
    stopCamera()
  }
})

// 切换摄像头
async function toggleCamera() {
  if (cameraActive.value) {
    stopCamera()
  } else {
    await startCamera()
  }
}

// 开启摄像头
async function startCamera() {
  if (!selectedScene.value) {
    ElMessage.warning('请先选择检测场景')
    return
  }
  
  try {
    // 获取摄像头权限
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 }
    })
    
    // 显示原始视频
    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream
    }
    
    // 连接 WebSocket（动态获取后端地址）
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = import.meta.env.DEV 
      ? `${window.location.hostname}:8888`  // 开发环境直连后端
      : window.location.host                  // 生产环境使用当前 host
    // WebSocket 认证：通过 query 参数传递 scene_id，token 由浏览器自动通过 cookie 发送
    const wsUrl = `${protocol}//${wsHost}/api/camera/detect?scene_id=${selectedScene.value}`
    ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      cameraActive.value = true
      ElMessage.success('摄像头连接成功')
      sendFrameLoop()
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'detection') {
        cameraDetections.value = data.detections || []
        cameraFps.value = data.fps || 0
        cameraObjects.value = data.total_objects || 0
        drawCameraDetections(data.detections)
      } else if (data.type === 'error') {
        ElMessage.error(data.message)
      }
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      ElMessage.error('连接错误')
      stopCamera()
    }
    
    ws.onclose = () => {
      cameraActive.value = false
    }
    
  } catch (error) {
    console.error('摄像头访问失败:', error)
    ElMessage.error('无法访问摄像头，请检查权限设置')
  }
}

// 停止摄像头
function stopCamera() {
  cameraActive.value = false
  
  // 停止 WebSocket
  if (ws) {
    ws.close()
    ws = null
  }
  
  // 停止媒体流
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop())
    mediaStream = null
  }
  
  // 停止动画帧
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
  
  cameraDetections.value = []
  cameraFps.value = 0
  cameraObjects.value = 0
}

// 循环发送帧
function sendFrameLoop() {
  if (!cameraActive.value || !ws || ws.readyState !== WebSocket.OPEN) return
  
  const video = videoRef.value
  if (!video || video.readyState < 2) {
    animationFrameId = requestAnimationFrame(sendFrameLoop)
    return
  }
  
  // 创建临时 canvas 抽帧
  const tempCanvas = document.createElement('canvas')
  tempCanvas.width = video.videoWidth
  tempCanvas.height = video.videoHeight
  const tempCtx = tempCanvas.getContext('2d')
  tempCtx.drawImage(video, 0, 0)
  
  // 转换为 JPEG 并发送
  tempCanvas.toBlob((blob) => {
    if (blob && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(blob)
    }
  }, 'image/jpeg', 0.7)
  
  // 控制发送频率（约 10fps）
  setTimeout(() => {
    animationFrameId = requestAnimationFrame(sendFrameLoop)
  }, 100)
}

// 绘制摄像头检测结果
function drawCameraDetections(detections) {
  const canvas = cameraCanvasRef.value
  const video = videoRef.value
  if (!canvas || !video || video.readyState < 2) return
  
  // 设置 canvas 尺寸与视频一致
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  
  const ctx = canvas.getContext('2d')
  
  // 绘制当前视频帧
  ctx.drawImage(video, 0, 0)
  
  // 绘制检测框
  detections.forEach(det => {
    const [x1, y1, x2, y2] = det.bbox
    
    // 绘制边界框
    ctx.strokeStyle = '#67c23a'
    ctx.lineWidth = 2
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
    
    // 绘制标签背景
    const label = `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`
    ctx.font = '14px Arial'
    const textWidth = ctx.measureText(label).width
    ctx.fillStyle = '#67c23a'
    ctx.fillRect(x1, y1 - 24, textWidth + 10, 24)
    
    // 绘制标签文字
    ctx.fillStyle = '#fff'
    ctx.fillText(label, x1 + 5, y1 - 6)
  })
}

onMounted(() => {
  loadScenes()
})

onUnmounted(() => {
  stopCamera()
})
</script>

<style lang="scss" scoped>
.detection-page {
  display: flex;
  height: calc(100vh - #{$header-height} - 40px);
  background: $bg-color;
}

.control-panel {
  width: 320px;
  background: #fff;
  border-right: 1px solid #ebeef5;
  padding: $spacing-lg;
  overflow-y: auto;

  h3 {
    margin: 0 0 $spacing-lg;
    font-size: 18px;
    color: $text-primary;
  }

  .control-section {
    margin-bottom: $spacing-lg;

    label {
      display: block;
      margin-bottom: $spacing-sm;
      font-size: 14px;
      color: $text-regular;
    }

    .el-select,
    .el-radio-group {
      width: 100%;
    }

    .scene-category {
      float: right;
      color: $text-secondary;
      font-size: 12px;
    }

    .optional-hint {
      color: $text-placeholder;
      font-size: 12px;
    }
  }

  .detect-btn {
    width: 100%;
    margin-top: $spacing-md;
  }
}

.result-panel {
  flex: 1;
  padding: $spacing-lg;
  overflow-y: auto;
}

.result-content {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $spacing-lg;

  h3 {
    margin: 0;
    font-size: 18px;
    color: $text-primary;
  }

  .result-stats {
    display: flex;
    gap: $spacing-sm;
  }
}

.image-container {
  margin-bottom: $spacing-lg;
  text-align: center;

  .detection-canvas {
    max-width: 100%;
    max-height: 500px;
    border: 1px solid #ebeef5;
    border-radius: $border-radius-md;
  }
}

.batch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: $spacing-lg;
  margin-bottom: $spacing-lg;
}

.batch-item {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: $border-radius-md;
  padding: $spacing-md;

  .batch-item-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-sm;

    .batch-filename {
      font-weight: 500;
      font-size: 14px;
      color: $text-primary;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 60%;
    }

    .batch-item-stats {
      display: flex;
      gap: 4px;
    }
  }

  .batch-canvas-wrap {
    text-align: center;
    margin-bottom: $spacing-sm;

    .detection-canvas {
      max-width: 100%;
      max-height: 280px;
      border: 1px solid #ebeef5;
      border-radius: $border-radius-sm;
    }
  }

  .batch-no-detection {
    text-align: center;
    padding: $spacing-sm;
    color: $text-placeholder;
    font-size: 13px;
  }
}

.video-container {
  margin-bottom: $spacing-lg;
  text-align: center;

  .detection-video {
    max-width: 100%;
    max-height: 500px;
    border-radius: $border-radius-md;
  }
}

.detection-details {
  h4 {
    margin: 0 0 $spacing-md;
    font-size: 16px;
    color: $text-primary;
  }
}

.empty-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: #fff;
  border-radius: $border-radius-lg;
  color: $text-secondary;

  p {
    margin: $spacing-md 0 0;
    font-size: 16px;
  }

  .hint {
    font-size: 14px;
    color: $text-placeholder;
  }
}

.camera-container {
  background: #fff;
  border-radius: $border-radius-lg;
  padding: $spacing-lg;

  .camera-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-lg;

    h3 {
      margin: 0;
      font-size: 18px;
      color: $text-primary;
    }

    .camera-stats {
      display: flex;
      gap: $spacing-sm;
    }
  }

  .camera-view {
    display: flex;
    gap: $spacing-lg;
    margin-bottom: $spacing-lg;

    .video-wrapper {
      flex: 1;

      h4 {
        margin: 0 0 $spacing-sm;
        font-size: 14px;
        color: $text-regular;
      }
    }

    .camera-video,
    .camera-canvas {
      width: 100%;
      max-height: 360px;
      border: 1px solid #ebeef5;
      border-radius: $border-radius-md;
      background: #000;
    }
  }

  .detection-details {
    h4 {
      margin: 0 0 $spacing-md;
      font-size: 16px;
      color: $text-primary;
    }
  }
}
</style>
