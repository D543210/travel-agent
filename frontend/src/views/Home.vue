<template>
  <div class="home-container">
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <!-- 页面标题 -->
    <div class="page-header">
      <div class="icon-wrapper">
        <span class="icon">✈️</span>
      </div>
      <h1 class="page-title">智能旅行助手</h1>
      <p class="page-subtitle">基于AI的个性化旅行规划,让每一次出行都完美无忧</p>
    </div>

    <a-card class="form-card" :bordered="false">
      <a-form
        :model="formData"
        layout="vertical"
        @finish="handleSubmit"
      >
        <!-- 第一步:目的地和日期 -->
        <div class="form-section">
          <div class="section-header">
            <span class="section-icon">📍</span>
            <span class="section-title">目的地与日期</span>
          </div>

          <a-row :gutter="24">
            <a-col :span="8">
              <a-form-item name="city" :rules="[{ required: true, message: '请输入目的地城市' }]">
                <template #label>
                  <span class="form-label">目的地城市</span>
                </template>
                <a-input
                  v-model:value="formData.city"
                  placeholder="例如: 北京"
                  size="large"
                  class="custom-input"
                >
                  <template #prefix>
                    <span style="color: #1890ff;">🏙️</span>
                  </template>
                </a-input>
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item name="start_date" :rules="[{ required: true, message: '请选择开始日期' }]">
                <template #label>
                  <span class="form-label">开始日期</span>
                </template>
                <a-date-picker
                  v-model:value="formData.start_date"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item name="end_date" :rules="[{ required: true, message: '请选择结束日期' }]">
                <template #label>
                  <span class="form-label">结束日期</span>
                </template>
                <a-date-picker
                  v-model:value="formData.end_date"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>
            <a-col :span="4">
              <a-form-item>
                <template #label>
                  <span class="form-label">旅行天数</span>
                </template>
                <div class="days-display-compact">
                  <span class="days-value">{{ formData.travel_days }}</span>
                  <span class="days-unit">天</span>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
          <a-space direction="vertical">
            <a-checkbox v-model:checked="useSavedPreferences">
              使用已保存的长期偏好
            </a-checkbox>
            <a-checkbox v-model:checked="saveCurrentPreferences">
              保存这些偏好，供以后行程使用
            </a-checkbox>
          </a-space>
        </div>

        <!-- 第二步:偏好设置 -->
        <div class="form-section">
          <div class="section-header">
            <span class="section-icon">⚙️</span>
            <span class="section-title">偏好设置</span>
          </div>

          <a-row :gutter="24">
            <a-col :span="8">
              <a-form-item name="transportation">
                <template #label>
                  <span class="form-label">交通方式</span>
                </template>
                <a-select v-model:value="formData.transportation" size="large" class="custom-select">
                  <a-select-option value="公共交通">🚇 公共交通</a-select-option>
                  <a-select-option value="自驾">🚗 自驾</a-select-option>
                  <a-select-option value="步行">🚶 步行</a-select-option>
                  <a-select-option value="混合">🔀 混合</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item name="accommodation">
                <template #label>
                  <span class="form-label">住宿偏好</span>
                </template>
                <a-select v-model:value="formData.accommodation" size="large" class="custom-select">
                  <a-select-option value="经济型酒店">💰 经济型酒店</a-select-option>
                  <a-select-option value="舒适型酒店">🏨 舒适型酒店</a-select-option>
                  <a-select-option value="豪华酒店">⭐ 豪华酒店</a-select-option>
                  <a-select-option value="民宿">🏡 民宿</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item name="preferences">
                <template #label>
                  <span class="form-label">旅行偏好</span>
                </template>
                <div class="preference-tags">
                  <a-checkbox-group v-model:value="formData.preferences" class="custom-checkbox-group">
                    <a-checkbox value="历史文化" class="preference-tag">🏛️ 历史文化</a-checkbox>
                    <a-checkbox value="自然风光" class="preference-tag">🏞️ 自然风光</a-checkbox>
                    <a-checkbox value="美食" class="preference-tag">🍜 美食</a-checkbox>
                    <a-checkbox value="购物" class="preference-tag">🛍️ 购物</a-checkbox>
                    <a-checkbox value="艺术" class="preference-tag">🎨 艺术</a-checkbox>
                    <a-checkbox value="休闲" class="preference-tag">☕ 休闲</a-checkbox>
                  </a-checkbox-group>
                </div>
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="24">
            <a-col :span="12">
              <a-form-item label="饮食限制">
                <a-select
                  v-model:value="dietaryRestrictions"
                  mode="tags"
                  :max-tag-count="6"
                  placeholder="例如：素食、无麸质、海鲜过敏"
                  size="large"
                />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="旅行节奏">
                <a-select v-model:value="travelPace" allow-clear placeholder="选择旅行节奏" size="large">
                  <a-select-option value="舒缓">舒缓：减少景点，留出休息时间</a-select-option>
                  <a-select-option value="适中">适中：游览与休息平衡</a-select-option>
                  <a-select-option value="紧凑">紧凑：尽可能多安排景点</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>

          <div class="saved-preferences-panel">
            <template v-if="savedPreferences">
              <div class="saved-preferences-summary">
                <strong>已保存的长期偏好：</strong>
                <span>{{ savedPreferenceSummary }}</span>
              </div>
              <a-space wrap>
                <a-button size="small" @click="applySavedPreferences">
                  应用到当前表单
                </a-button>
                <a-button size="small" @click="saveCurrentPreferenceNow">
                  用当前表单更新
                </a-button>
                <a-popconfirm
                  title="确定删除已保存的长期偏好吗？"
                  ok-text="删除"
                  cancel-text="取消"
                  @confirm="removeSavedPreferences"
                >
                  <a-button size="small" danger>删除长期偏好</a-button>
                </a-popconfirm>
              </a-space>
            </template>
            <template v-else>
              <span class="saved-preferences-empty">目前没有已保存的长期偏好。</span>
              <a-button size="small" type="link" @click="saveCurrentPreferenceNow">
                保存当前表单偏好
              </a-button>
            </template>
          </div>
        </div>

        <!-- 第三步:额外要求 -->
        <div class="form-section">
          <div class="section-header">
            <span class="section-icon">💬</span>
            <span class="section-title">额外要求</span>
          </div>

          <a-form-item name="free_text_input">
            <a-textarea
              v-model:value="formData.free_text_input"
              placeholder="请输入您的额外要求,例如:想去看升旗、需要无障碍设施、对海鲜过敏等..."
              :rows="3"
              size="large"
              class="custom-textarea"
            />
          </a-form-item>
        </div>

        <!-- 提交按钮 -->
        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            :loading="loading"
            size="large"
            block
            class="submit-button"
          >
            <template v-if="!loading">
              <span class="button-icon">🚀</span>
              <span>开始规划我的旅行</span>
            </template>
            <template v-else>
              <span>正在生成中...</span>
            </template>
          </a-button>
        </a-form-item>

        <!-- 加载进度条 -->
        <a-form-item v-if="loading">
          <div class="loading-container">
            <a-progress
              :percent="loadingProgress"
              status="active"
              :stroke-color="{
                '0%': '#667eea',
                '100%': '#764ba2',
              }"
              :stroke-width="10"
            />
            <p class="loading-status">
              {{ loadingStatus }}
            </p>
          </div>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  createTripPlanningJob,
  deletePreferences,
  getPreferences,
  getPlanningJob,
  savePreferences
} from '@/services/api'
import type { PlanningJob, TripFormData, UserPreference } from '@/types'
import type { Dayjs } from 'dayjs'

const router = useRouter()
const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')
const useSavedPreferences = ref(false)
const saveCurrentPreferences = ref(false)
const savedPreferences = ref<UserPreference | null>(null)
const dietaryRestrictions = ref<string[]>([])
const travelPace = ref<string | undefined>()
let pollingCancelled = false

const savedPreferenceSummary = computed(() => {
  const preference = savedPreferences.value
  if (!preference) return ''
  return [
    preference.attraction_types.length
      ? `景点：${preference.attraction_types.join('、')}`
      : '',
    preference.transportation_preference
      ? `交通：${preference.transportation_preference}`
      : '',
    preference.accommodation_preference
      ? `住宿：${preference.accommodation_preference}`
      : '',
    preference.dietary_restrictions.length
      ? `饮食限制：${preference.dietary_restrictions.join('、')}`
      : '',
    preference.travel_pace ? `节奏：${preference.travel_pace}` : ''
  ].filter(Boolean).join('；') || '尚未设置具体偏好'
})

type TripFormState = Omit<TripFormData, 'start_date' | 'end_date'> & {
  start_date: Dayjs | null
  end_date: Dayjs | null
}

const formData = reactive<TripFormState>({
  city: '',
  start_date: null,
  end_date: null,
  travel_days: 1,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: ''
})

// 监听日期变化,自动计算旅行天数
watch([() => formData.start_date, () => formData.end_date], ([start, end]) => {
  if (start && end) {
    const days = end.diff(start, 'day') + 1
    if (days > 0 && days <= 5) {
      formData.travel_days = days
    } else if (days > 5) {
      message.warning('旅行天数不能超过5天')
      formData.end_date = null
    } else {
      message.warning('结束日期不能早于开始日期')
      formData.end_date = null
    }
  }
})

const preferenceFromCurrentForm = (): UserPreference => ({
  attraction_types: [...formData.preferences],
  dietary_restrictions: [...dietaryRestrictions.value],
  travel_pace: travelPace.value || null,
  transportation_preference: formData.transportation,
  accommodation_preference: formData.accommodation
})

const saveCurrentPreferenceNow = async () => {
  try {
    savedPreferences.value = await savePreferences(preferenceFromCurrentForm())
    useSavedPreferences.value = true
    message.success('长期偏好已保存')
  } catch (error: any) {
    message.error(error.response?.data?.detail?.message || '保存长期偏好失败')
  }
}

const applySavedPreferences = () => {
  const preference = savedPreferences.value
  if (!preference) return
  formData.preferences = [...preference.attraction_types]
  dietaryRestrictions.value = [...preference.dietary_restrictions]
  travelPace.value = preference.travel_pace || undefined
  if (preference.transportation_preference) {
    formData.transportation = preference.transportation_preference
  }
  if (preference.accommodation_preference) {
    formData.accommodation = preference.accommodation_preference
  }
  useSavedPreferences.value = true
  message.success('已将长期偏好应用到当前表单')
}

const removeSavedPreferences = async () => {
  try {
    await deletePreferences()
    savedPreferences.value = null
    useSavedPreferences.value = false
    message.success('长期偏好已删除')
  } catch (error: any) {
    message.error(error.response?.data?.detail?.message || '删除长期偏好失败')
  }
}

const finishPlanningJob = async (job: PlanningJob) => {
  loadingProgress.value = 100
  loadingStatus.value = '✅ 行程已生成'
  sessionStorage.setItem('activeTripVersion', String(job.result_version || 1))
  sessionStorage.removeItem('activeJobId')
  message.success('旅行计划生成成功!')
  await router.push({ name: 'TripResult', params: { tripId: job.trip_id } })
}

const pollPlanningJob = async (jobId: string) => {
  const deadline = Date.now() + 45 * 60 * 1000
  while (!pollingCancelled && Date.now() < deadline) {
    const job = await getPlanningJob(jobId)
    loadingProgress.value = job.progress_percent
    loadingStatus.value = job.progress_message
    if (job.status === 'failed') {
      sessionStorage.removeItem('activeJobId')
      throw new Error(job.error_message || `任务在${job.stage}阶段失败`)
    }
    if (job.status === 'succeeded') {
      await finishPlanningJob(job)
      return
    }
    await new Promise(resolve => setTimeout(resolve, 1500))
  }
  if (!pollingCancelled) {
    throw new Error('任务等待时间过长，请到“我的行程”查看状态')
  }
}

onBeforeUnmount(() => {
  pollingCancelled = true
})

onMounted(async () => {
  pollingCancelled = false
  try {
    savedPreferences.value = await getPreferences()
  } catch {
    savedPreferences.value = null
  }

  const activeJobId = sessionStorage.getItem('activeJobId')
  const activeTripId = sessionStorage.getItem('activeTripId')
  if (!activeJobId || !activeTripId) return

  loading.value = true
  loadingStatus.value = '正在恢复后台任务进度...'
  try {
    await pollPlanningJob(activeJobId)
  } catch (error: any) {
    message.error(error.message || '恢复后台任务失败')
  } finally {
    loading.value = false
  }
})

const handleSubmit = async () => {
  if (!formData.start_date || !formData.end_date) {
    message.error('请选择日期')
    return
  }

  loading.value = true
  loadingProgress.value = 0
  loadingStatus.value = '正在创建后台任务...'

  try {
    const requestData = {
      city: formData.city,
      start_date: formData.start_date.format('YYYY-MM-DD'),
      end_date: formData.end_date.format('YYYY-MM-DD'),
      travel_days: formData.travel_days,
      transportation: formData.transportation,
      accommodation: formData.accommodation,
      preferences: formData.preferences,
      free_text_input: formData.free_text_input,
      use_saved_preferences: useSavedPreferences.value
    }

    if (saveCurrentPreferences.value) {
      savedPreferences.value = await savePreferences(preferenceFromCurrentForm())
    }

    const created = await createTripPlanningJob(requestData)
    sessionStorage.setItem('activeTripId', created.trip_id)
    sessionStorage.setItem('activeJobId', created.job_id)

    await pollPlanningJob(created.job_id)
  } catch (error: any) {
    message.error(
      error.response?.data?.detail?.message ||
      error.message ||
      '生成旅行计划失败,请稍后重试'
    )
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 60px 20px;
  position: relative;
  overflow: hidden;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: hidden;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  animation: float 20s infinite ease-in-out;
}

.circle-1 {
  width: 300px;
  height: 300px;
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.circle-2 {
  width: 200px;
  height: 200px;
  top: 50%;
  right: -50px;
  animation-delay: 5s;
}

.circle-3 {
  width: 150px;
  height: 150px;
  bottom: -50px;
  left: 30%;
  animation-delay: 10s;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) rotate(0deg);
  }
  50% {
    transform: translateY(-30px) rotate(180deg);
  }
}

/* 页面标题 */
.page-header {
  text-align: center;
  margin-bottom: 50px;
  animation: fadeInDown 0.8s ease-out;
  position: relative;
  z-index: 1;
}

.icon-wrapper {
  margin-bottom: 20px;
}

.icon {
  font-size: 80px;
  display: inline-block;
  animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20px);
  }
}

.page-title {
  font-size: 56px;
  font-weight: 800;
  color: #ffffff;
  margin-bottom: 16px;
  text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.3);
  letter-spacing: 2px;
}

.page-subtitle {
  font-size: 20px;
  color: rgba(255, 255, 255, 0.95);
  margin: 0;
  font-weight: 300;
}

/* 表单卡片 */
.form-card {
  max-width: 1400px;
  margin: 0 auto;
  border-radius: 24px;
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.4);
  animation: fadeInUp 0.8s ease-out;
  position: relative;
  z-index: 1;
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.98) !important;
}

/* 表单分区 */
.form-section {
  margin-bottom: 32px;
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 16px;
  border: 1px solid #e8e8e8;
  transition: all 0.3s ease;
}

.form-section:hover {
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.15);
  transform: translateY(-2px);
}

.section-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid #667eea;
}

.section-icon {
  font-size: 24px;
  margin-right: 12px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

/* 表单标签 */
.form-label {
  font-size: 15px;
  font-weight: 500;
  color: #555;
}

/* 自定义输入框 */
.custom-input :deep(.ant-input),
.custom-input :deep(.ant-picker) {
  border-radius: 12px;
  border: 2px solid #e8e8e8;
  transition: all 0.3s ease;
}

.custom-input :deep(.ant-input:hover),
.custom-input :deep(.ant-picker:hover) {
  border-color: #667eea;
}

.custom-input :deep(.ant-input:focus),
.custom-input :deep(.ant-picker-focused) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* 自定义选择框 */
.custom-select :deep(.ant-select-selector) {
  border-radius: 12px !important;
  border: 2px solid #e8e8e8 !important;
  transition: all 0.3s ease;
}

.custom-select:hover :deep(.ant-select-selector) {
  border-color: #667eea !important;
}

.custom-select :deep(.ant-select-focused .ant-select-selector) {
  border-color: #667eea !important;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

/* 天数显示 - 紧凑版 */
.days-display-compact {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.days-display-compact .days-value {
  font-size: 24px;
  font-weight: 700;
  margin-right: 4px;
}

.days-display-compact .days-unit {
  font-size: 14px;
}

/* 偏好标签 */
.preference-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.custom-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

.saved-preferences-panel {
  margin-top: 20px;
  padding: 14px 16px;
  border: 1px solid #d9dff7;
  border-radius: 12px;
  background: #f7f8ff;
}

.saved-preferences-summary {
  margin-bottom: 12px;
  color: #4a4f68;
  line-height: 1.7;
}

.saved-preferences-empty {
  color: #777;
}

.preference-tag :deep(.ant-checkbox-wrapper) {
  margin: 0 !important;
  padding: 8px 16px;
  border: 2px solid #e8e8e8;
  border-radius: 20px;
  transition: all 0.3s ease;
  background: white;
  font-size: 14px;
}

.preference-tag :deep(.ant-checkbox-wrapper:hover) {
  border-color: #667eea;
  background: #f5f7ff;
}

.preference-tag :deep(.ant-checkbox-wrapper-checked) {
  border-color: #667eea;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

/* 自定义文本域 */
.custom-textarea :deep(.ant-input) {
  border-radius: 12px;
  border: 2px solid #e8e8e8;
  transition: all 0.3s ease;
}

.custom-textarea :deep(.ant-input:hover) {
  border-color: #667eea;
}

.custom-textarea :deep(.ant-input:focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

/* 提交按钮 */
.submit-button {
  height: 56px;
  border-radius: 28px;
  font-size: 18px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.submit-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(102, 126, 234, 0.5);
}

.submit-button:active {
  transform: translateY(0);
}

.button-icon {
  margin-right: 8px;
  font-size: 20px;
}

/* 加载容器 */
.loading-container {
  text-align: center;
  padding: 24px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 16px;
  border: 2px dashed #667eea;
}

.loading-status {
  margin-top: 16px;
  color: #667eea;
  font-size: 18px;
  font-weight: 500;
}

/* 动画 */
@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
