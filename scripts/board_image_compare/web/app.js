const elements = {
  serviceStatus: document.querySelector('#service-status'),
  originalDirectory: document.querySelector('#original-directory'),
  referenceDirectoryLabel: document.querySelector('#reference-directory-label'),
  referencePreviewLabel: document.querySelector('#reference-preview-label'),
  referenceModes: document.querySelectorAll('[data-reference-mode]'),
  originalCount: document.querySelector('#original-count'),
  reconstructionDirectory: document.querySelector('#reconstruction-directory'),
  boardResource: document.querySelector('#board-resource'),
  sourceSelect: document.querySelector('#reconstruction-source'),
  jobSelect: document.querySelector('#job-select'),
  refreshJobs: document.querySelector('#refresh-jobs'),
  pullImage: document.querySelector('#pull-image'),
  qualityAssistance: document.querySelector('#quality-assistance'),
  originalPreview: document.querySelector('#original-preview'),
  reconstructionPreview: document.querySelector('#reconstruction-preview'),
  originalEmpty: document.querySelector('#original-empty'),
  reconstructionEmpty: document.querySelector('#reconstruction-empty'),
  originalName: document.querySelector('#original-name'),
  reconstructionName: document.querySelector('#reconstruction-name'),
  qualityMarker: document.querySelector('#quality-marker'),
  qualityPsnr: document.querySelector('#quality-psnr'),
  qualitySsim: document.querySelector('#quality-ssim'),
  previousImage: document.querySelector('#previous-image'),
  nextImage: document.querySelector('#next-image'),
  imageIndex: document.querySelector('#image-index'),
  imageTotal: document.querySelector('#image-total'),
  pullStatus: document.querySelector('#pull-status'),
  thumbnailStrip: document.querySelector('#thumbnail-strip'),
}

const state = {
  config: null,
  sourceId: '',
  sourceEpoch: 0,
  jobs: [],
  detail: null,
  index: 0,
  quality: {},
  qualityEnabled: false,
  referenceMode: 'original',
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.message || `HTTP ${response.status}`)
  return payload
}

function currentJobId() {
  return elements.jobSelect.value
}

function currentPair() {
  return state.detail?.pairs?.[state.index] || null
}

function isCurrentSourceRequest(sourceEpoch, sourceId) {
  return sourceEpoch === state.sourceEpoch && sourceId === state.sourceId
}

function isCurrentJobRequest(sourceEpoch, sourceId, jobId) {
  return isCurrentSourceRequest(sourceEpoch, sourceId) && jobId === currentJobId()
}

function isCurrentPullRequest(request) {
  return isCurrentJobRequest(request.sourceEpoch, request.sourceId, request.jobId)
    && request.index === state.index
    && request.referenceMode === state.referenceMode
    && request.pair === currentPair()
}

function showImage(image, empty, url) {
  if (!url) {
    image.classList.remove('visible')
    image.removeAttribute('src')
    empty.hidden = false
    return
  }
  image.onload = () => {
    image.classList.add('visible')
    empty.hidden = true
  }
  image.onerror = () => {
    image.classList.remove('visible')
    empty.hidden = false
  }
  image.src = `${url}&v=${Date.now()}`
}

function qualityFor(index) {
  return state.quality[`${currentJobId()}:${index}:${state.referenceMode}`] || null
}

function referenceAvailable(pair) {
  return state.referenceMode === 'pytorch' ? pair?.pytorch_available : pair?.original_available
}

function renderReferenceMode() {
  const isPytorch = state.referenceMode === 'pytorch'
  elements.referenceDirectoryLabel.textContent = isPytorch ? 'PyTorch 参考目录' : '原图目录'
  elements.referencePreviewLabel.textContent = isPytorch ? 'PyTorch' : '原图'
  elements.originalDirectory.textContent = isPytorch
    ? (state.config?.pytorch_manifest || '未生成 PyTorch 参考图')
    : (state.config?.original_dir || '未配置')
  for (const button of elements.referenceModes) {
    const active = button.dataset.referenceMode === state.referenceMode
    button.classList.toggle('active', active)
    button.setAttribute('aria-pressed', String(active))
  }
}

function renderPreview() {
  const pair = currentPair()
  const total = state.detail?.pair_count || 0
  elements.imageIndex.value = total ? String(state.index + 1) : '1'
  elements.imageIndex.max = String(Math.max(1, total))
  elements.imageTotal.textContent = `/ ${total}`
  elements.previousImage.disabled = state.index <= 0
  elements.nextImage.disabled = state.index >= total - 1
  elements.pullImage.disabled = !pair || !pair.reconstruction_available
  const quality = pair ? qualityFor(state.index) : null
  const psnr = Number(quality?.psnr_db)
  const ssim = Number(quality?.ssim)
  elements.qualityPsnr.textContent = Number.isFinite(psnr) ? psnr.toFixed(2) : '--'
  elements.qualitySsim.textContent = Number.isFinite(ssim) ? ssim.toFixed(4) : '--'

  if (!pair) {
    showImage(elements.originalPreview, elements.originalEmpty, '')
    showImage(elements.reconstructionPreview, elements.reconstructionEmpty, '')
    return
  }

  elements.originalName.textContent = referenceAvailable(pair)
    ? (pair.original_name || `第 ${state.index + 1} 张`)
    : (state.referenceMode === 'pytorch' ? 'PyTorch 参考图缺失' : '原图缺失')
  elements.reconstructionName.textContent = pair.reconstruction_name || '重建图缺失'
  showImage(
    elements.originalPreview,
    elements.originalEmpty,
    referenceAvailable(pair)
      ? `/api/image/reference?job_id=${encodeURIComponent(currentJobId())}&index=${state.index}&mode=${state.referenceMode}`
      : '',
  )
  showImage(
    elements.reconstructionPreview,
    elements.reconstructionEmpty,
    pair.cached ? `/api/image/reconstruction?job_id=${encodeURIComponent(currentJobId())}&index=${state.index}` : '',
  )
  elements.reconstructionEmpty.textContent = pair.reconstruction_available
    ? '点击“拉取”获取当前图片'
    : '当前序号没有重建图'
  const marked = state.qualityEnabled && quality?.suspected
  elements.qualityMarker.hidden = !marked
  elements.qualityMarker.title = marked
    ? `PSNR ${Number(quality.psnr_db).toFixed(2)} dB / SSIM ${Number(quality.ssim).toFixed(3)} / ${quality.reason}`
    : ''
  renderThumbnails()
}

function renderThumbnails() {
  elements.thumbnailStrip.replaceChildren()
  const pairs = state.detail?.pairs || []
  const start = Math.max(0, state.index - 5)
  const end = Math.min(pairs.length, state.index + 6)
  for (let index = start; index < end; index += 1) {
    const pair = pairs[index]
    const button = document.createElement('button')
    button.type = 'button'
    button.className = `thumbnail${index === state.index ? ' active' : ''}`
    button.title = `第 ${index + 1} 张`
    if (referenceAvailable(pair)) {
      const image = document.createElement('img')
      image.loading = 'lazy'
      image.alt = ''
      image.src = `/api/image/reference?job_id=${encodeURIComponent(currentJobId())}&index=${index}&mode=${state.referenceMode}`
      button.append(image)
    }
    const label = document.createElement('span')
    label.className = 'index'
    label.textContent = String(index + 1)
    button.append(label)
    if (state.qualityEnabled && qualityFor(index)?.suspected) {
      const dot = document.createElement('span')
      dot.className = 'quality-dot'
      button.append(dot)
    }
    button.addEventListener('click', () => setIndex(index))
    elements.thumbnailStrip.append(button)
  }
}

function setIndex(index) {
  const total = state.detail?.pair_count || 0
  state.index = Math.max(0, Math.min(index, Math.max(0, total - 1)))
  elements.pullStatus.textContent = currentPair()?.cached ? '已从本地缓存加载' : '当前重建图尚未拉取'
  renderPreview()
}

function resetSelectedJob() {
  state.sourceEpoch += 1
  state.jobs = []
  state.detail = null
  state.index = 0
  state.quality = {}
  elements.jobSelect.replaceChildren()
  elements.reconstructionDirectory.textContent = '未选择 job'
  elements.originalCount.textContent = '0 张'
  elements.originalName.textContent = '未选择'
  elements.reconstructionName.textContent = '未拉取'
  elements.qualityMarker.hidden = true
  elements.qualityMarker.title = ''
  elements.qualityPsnr.textContent = '--'
  elements.qualitySsim.textContent = '--'
  elements.thumbnailStrip.replaceChildren()
  elements.pullImage.disabled = true
  elements.pullStatus.textContent = '等待选择 job'
  showImage(elements.originalPreview, elements.originalEmpty, '')
  showImage(elements.reconstructionPreview, elements.reconstructionEmpty, '')
}

async function loadJob(jobId) {
  if (!jobId) return
  const sourceId = state.sourceId
  const sourceEpoch = state.sourceEpoch
  elements.pullStatus.textContent = '正在读取 job 清单'
  const detail = await requestJson(`/api/job?id=${encodeURIComponent(jobId)}`)
  if (!isCurrentJobRequest(sourceEpoch, sourceId, jobId)) return
  state.detail = detail
  elements.reconstructionDirectory.textContent = state.detail.job.path
  elements.originalCount.textContent = `${state.detail.pairs.filter(referenceAvailable).length} 张`
  setIndex(Math.min(state.index, Math.max(0, state.detail.pair_count - 1)))
}

async function loadJobs() {
  const sourceId = state.sourceId
  const sourceEpoch = state.sourceEpoch
  elements.refreshJobs.disabled = true
  try {
    const payload = await requestJson(`/api/jobs?source=${encodeURIComponent(sourceId)}`)
    if (!isCurrentSourceRequest(sourceEpoch, sourceId)) return
    state.jobs = payload.jobs
    elements.jobSelect.replaceChildren()
    for (const job of state.jobs) {
      const option = document.createElement('option')
      option.value = job.id
      option.textContent = job.name
      elements.jobSelect.append(option)
    }
    if (state.jobs.length) await loadJob(state.jobs[0].id)
    else elements.pullStatus.textContent = '当前来源没有可用重建 job'
  } finally {
    if (isCurrentSourceRequest(sourceEpoch, sourceId)) {
      elements.refreshJobs.disabled = false
    }
  }
}

async function selectSource(sourceId) {
  state.sourceId = sourceId
  resetSelectedJob()
  await loadJobs()
}

async function pullCurrent() {
  const pair = currentPair()
  if (!pair) return
  const request = {
    sourceEpoch: state.sourceEpoch,
    sourceId: state.sourceId,
    jobId: currentJobId(),
    index: state.index,
    referenceMode: state.referenceMode,
    pair,
  }
  elements.pullImage.disabled = true
  elements.pullStatus.textContent = `正在拉取第 ${request.index + 1} 张`
  try {
    const payload = await requestJson('/api/pull', {
      method: 'POST',
      body: JSON.stringify({
        job_id: request.jobId,
        index: request.index,
        reference_mode: request.referenceMode,
      }),
    })
    if (!isCurrentPullRequest(request)) return
    pair.cached = true
    if (payload.quality) {
      const { jobId, index, referenceMode } = request
      state.quality[`${jobId}:${index}:${referenceMode}`] = payload.quality
    }
    elements.pullStatus.textContent = payload.cached ? '已从本地缓存加载' : '拉取完成'
    renderPreview()
  } catch (error) {
    if (!isCurrentPullRequest(request)) return
    elements.pullStatus.textContent = `拉取失败：${error.message}`
  } finally {
    if (isCurrentPullRequest(request)) {
      elements.pullImage.disabled = false
    }
  }
}

async function setQualityAssistance(enabled) {
  state.qualityEnabled = enabled
  await requestJson('/api/quality-scan', {
    method: 'POST',
    body: JSON.stringify({ enabled, job_id: currentJobId() }),
  })
  renderPreview()
}

async function pollState() {
  const sourceEpoch = state.sourceEpoch
  const sourceId = state.sourceId
  try {
    const payload = await requestJson('/api/state')
    if (!isCurrentSourceRequest(sourceEpoch, sourceId)) return
    state.quality = payload.quality || {}
    const resources = payload.resources
    elements.boardResource.textContent = resources
      ? `CPU ${resources.cpu_percent.toFixed(1)}% · MEM ${resources.memory_percent.toFixed(1)}%`
      : '板端资源待采样'
    renderPreview()
  } catch (error) {
    if (!isCurrentSourceRequest(sourceEpoch, sourceId)) return
    elements.serviceStatus.textContent = `服务状态不可用：${error.message}`
  }
}

async function initialize() {
  try {
    state.config = await requestJson('/api/config')
    state.sourceId = state.config.default_source
    elements.sourceSelect.replaceChildren()
    for (const source of state.config.sources || []) {
      const option = document.createElement('option')
      option.value = source.id
      option.textContent = source.label
      elements.sourceSelect.append(option)
    }
    elements.sourceSelect.value = state.sourceId
    renderReferenceMode()
    elements.serviceStatus.textContent = `上位机服务已连接 · 板端 ${state.config.board_host}`
    await selectSource(state.sourceId)
    setInterval(pollState, 3000)
  } catch (error) {
    elements.serviceStatus.textContent = `初始化失败：${error.message}`
  }
}

elements.refreshJobs.addEventListener('click', loadJobs)
const sourceSelect = elements.sourceSelect
sourceSelect.addEventListener('change', () => selectSource(sourceSelect.value))
elements.jobSelect.addEventListener('change', () => loadJob(currentJobId()))
elements.pullImage.addEventListener('click', pullCurrent)
elements.previousImage.addEventListener('click', () => setIndex(state.index - 1))
elements.nextImage.addEventListener('click', () => setIndex(state.index + 1))
elements.imageIndex.addEventListener('change', () => setIndex(Number(elements.imageIndex.value) - 1))
elements.qualityAssistance.addEventListener('change', () => setQualityAssistance(elements.qualityAssistance.checked))
for (const button of elements.referenceModes) {
  button.addEventListener('click', () => {
    state.referenceMode = button.dataset.referenceMode || 'original'
    renderReferenceMode()
    if (state.detail) {
      elements.originalCount.textContent = `${state.detail.pairs.filter(referenceAvailable).length} 张`
    }
    renderPreview()
  })
}

initialize()
