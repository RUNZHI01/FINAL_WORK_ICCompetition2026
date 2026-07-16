const elements = {
  serviceStatus: document.querySelector('#service-status'),
  originalDirectory: document.querySelector('#original-directory'),
  originalCount: document.querySelector('#original-count'),
  reconstructionDirectory: document.querySelector('#reconstruction-directory'),
  boardResource: document.querySelector('#board-resource'),
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
  previousImage: document.querySelector('#previous-image'),
  nextImage: document.querySelector('#next-image'),
  imageIndex: document.querySelector('#image-index'),
  imageTotal: document.querySelector('#image-total'),
  pullStatus: document.querySelector('#pull-status'),
  thumbnailStrip: document.querySelector('#thumbnail-strip'),
}

const state = {
  config: null,
  jobs: [],
  detail: null,
  index: 0,
  quality: {},
  qualityEnabled: false,
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
  return state.quality[`${currentJobId()}:${index}`] || null
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

  if (!pair) {
    showImage(elements.originalPreview, elements.originalEmpty, '')
    showImage(elements.reconstructionPreview, elements.reconstructionEmpty, '')
    return
  }

  elements.originalName.textContent = pair.original_name || '原图缺失'
  elements.reconstructionName.textContent = pair.reconstruction_name || '重建图缺失'
  showImage(
    elements.originalPreview,
    elements.originalEmpty,
    pair.original_available ? `/api/image/original?job_id=${encodeURIComponent(currentJobId())}&index=${state.index}` : '',
  )
  showImage(
    elements.reconstructionPreview,
    elements.reconstructionEmpty,
    pair.cached ? `/api/image/reconstruction?job_id=${encodeURIComponent(currentJobId())}&index=${state.index}` : '',
  )
  elements.reconstructionEmpty.textContent = pair.reconstruction_available
    ? '点击“拉取”获取当前图片'
    : '当前序号没有重建图'
  const quality = qualityFor(state.index)
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
    if (pair.original_available) {
      const image = document.createElement('img')
      image.loading = 'lazy'
      image.alt = ''
      image.src = `/api/image/original?job_id=${encodeURIComponent(currentJobId())}&index=${index}`
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

async function loadJob(jobId) {
  if (!jobId) return
  elements.pullStatus.textContent = '正在读取 job 清单'
  state.detail = await requestJson(`/api/job?id=${encodeURIComponent(jobId)}`)
  elements.reconstructionDirectory.textContent = state.detail.job.path
  elements.originalCount.textContent = `${state.detail.pairs.filter((pair) => pair.original_available).length} 张`
  setIndex(Math.min(state.index, Math.max(0, state.detail.pair_count - 1)))
}

async function loadJobs() {
  elements.refreshJobs.disabled = true
  try {
    const payload = await requestJson('/api/jobs')
    state.jobs = payload.jobs
    elements.jobSelect.replaceChildren()
    for (const job of state.jobs) {
      const option = document.createElement('option')
      option.value = job.id
      option.textContent = job.name
      elements.jobSelect.append(option)
    }
    if (state.jobs.length) await loadJob(state.jobs[0].id)
    else elements.pullStatus.textContent = '板端没有可用重建 job'
  } finally {
    elements.refreshJobs.disabled = false
  }
}

async function pullCurrent() {
  const pair = currentPair()
  if (!pair) return
  elements.pullImage.disabled = true
  elements.pullStatus.textContent = `正在拉取第 ${state.index + 1} 张`
  try {
    const payload = await requestJson('/api/pull', {
      method: 'POST',
      body: JSON.stringify({ job_id: currentJobId(), index: state.index }),
    })
    pair.cached = true
    if (payload.quality) state.quality[`${currentJobId()}:${state.index}`] = payload.quality
    elements.pullStatus.textContent = payload.cached ? '已从本地缓存加载' : '拉取完成'
    renderPreview()
  } catch (error) {
    elements.pullStatus.textContent = `拉取失败：${error.message}`
  } finally {
    elements.pullImage.disabled = false
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
  try {
    const payload = await requestJson('/api/state')
    state.quality = payload.quality || {}
    const resources = payload.resources
    elements.boardResource.textContent = resources
      ? `CPU ${resources.cpu_percent.toFixed(1)}% · MEM ${resources.memory_percent.toFixed(1)}%`
      : '板端资源待采样'
    renderPreview()
  } catch (error) {
    elements.serviceStatus.textContent = `服务状态不可用：${error.message}`
  }
}

async function initialize() {
  try {
    state.config = await requestJson('/api/config')
    elements.originalDirectory.textContent = state.config.original_dir
    elements.serviceStatus.textContent = `上位机服务已连接 · 板端 ${state.config.board_host}`
    await loadJobs()
    setInterval(pollState, 3000)
  } catch (error) {
    elements.serviceStatus.textContent = `初始化失败：${error.message}`
  }
}

elements.refreshJobs.addEventListener('click', loadJobs)
elements.jobSelect.addEventListener('change', () => loadJob(currentJobId()))
elements.pullImage.addEventListener('click', pullCurrent)
elements.previousImage.addEventListener('click', () => setIndex(state.index - 1))
elements.nextImage.addEventListener('click', () => setIndex(state.index + 1))
elements.imageIndex.addEventListener('change', () => setIndex(Number(elements.imageIndex.value) - 1))
elements.qualityAssistance.addEventListener('change', () => setQualityAssistance(elements.qualityAssistance.checked))

initialize()
