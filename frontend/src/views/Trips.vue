<template>
  <div class="trips-page">
    <div class="trips-header">
      <div>
        <h1>我的行程</h1>
        <p>所有行程都保存在账号中，可跨设备访问。</p>
      </div>
      <a-space>
        <a-checkbox v-model:checked="includeArchived" @change="loadTrips">显示已归档</a-checkbox>
        <a-button type="primary" @click="router.push('/')">新建行程</a-button>
      </a-space>
    </div>

    <a-alert
      v-if="activeJobs.length"
      type="info"
      show-icon
      class="jobs-alert"
      :message="`有 ${activeJobs.length} 个后台任务正在处理`"
    >
      <template #description>
        <div v-for="job in activeJobs" :key="job.job_id" class="job-progress">
          <span>{{ job.progress_message }}</span>
          <a-progress :percent="job.progress_percent" size="small" />
        </div>
      </template>
    </a-alert>

    <a-spin :spinning="loading">
      <a-empty v-if="!loading && !trips.length" description="还没有行程">
        <a-button type="primary" @click="router.push('/')">创建第一条行程</a-button>
      </a-empty>
      <a-list v-else :data-source="trips" :grid="{ gutter: 20, xs: 1, sm: 1, md: 2, lg: 3 }">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-card hoverable @click="openTrip(item)">
              <template #title>{{ item.title }}</template>
              <template #extra>
                <a-tag :color="statusColor(item.status)">{{ statusText(item.status) }}</a-tag>
              </template>
              <p>当前版本：{{ item.current_version || '生成中' }}</p>
              <p>更新时间：{{ formatDate(item.updated_at) }}</p>
              <a-space @click.stop>
                <a-button v-if="item.current_version" type="primary" size="small" @click="openTrip(item)">
                  查看
                </a-button>
                <a-button v-if="!item.archived_at" size="small" danger @click="archive(item.trip_id)">
                  归档
                </a-button>
                <a-button v-else size="small" @click="restore(item.trip_id)">恢复</a-button>
              </a-space>
            </a-card>
          </a-list-item>
        </template>
      </a-list>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { archiveTrip, getPlanningJobs, getTrips, restoreTrip } from '@/services/api'
import type { PlanningJob, TripSummary } from '@/types'

const router = useRouter()
const loading = ref(false)
const includeArchived = ref(false)
const trips = ref<TripSummary[]>([])
const activeJobs = ref<PlanningJob[]>([])
let refreshTimer: number | undefined

const loadTrips = async () => {
  loading.value = true
  try {
    const [tripRows, jobs] = await Promise.all([
      getTrips(includeArchived.value),
      getPlanningJobs(true)
    ])
    trips.value = tripRows
    activeJobs.value = jobs
  } catch (error: any) {
    message.error(error.response?.data?.detail?.message || '加载行程失败')
  } finally {
    loading.value = false
  }
}

const openTrip = (trip: TripSummary) => {
  if (!trip.current_version) {
    message.info('行程仍在生成中')
    return
  }
  void router.push({ name: 'TripResult', params: { tripId: trip.trip_id } })
}

const archive = async (tripId: string) => {
  await archiveTrip(tripId)
  message.success('行程已归档')
  await loadTrips()
}

const restore = async (tripId: string) => {
  await restoreTrip(tripId)
  message.success('行程已恢复')
  await loadTrips()
}

const formatDate = (value: string) => new Date(value).toLocaleString('zh-CN')
const statusText = (status: TripSummary['status']) => ({ planning: '生成中', ready: '可用', failed: '失败' }[status])
const statusColor = (status: TripSummary['status']) => ({ planning: 'processing', ready: 'success', failed: 'error' }[status])

onMounted(loadTrips)
onMounted(() => {
  refreshTimer = window.setInterval(() => {
    if (activeJobs.value.length) void loadTrips()
  }, 2000)
})
onBeforeUnmount(() => {
  if (refreshTimer !== undefined) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.trips-page { max-width: 1200px; margin: 0 auto; padding: 24px; }
.trips-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.trips-header h1 { margin-bottom: 4px; }
.trips-header p { margin: 0; color: #777; }
.jobs-alert { margin-bottom: 20px; }
.job-progress + .job-progress { margin-top: 8px; }
@media (max-width: 768px) {
  .trips-header { align-items: flex-start; flex-direction: column; gap: 16px; }
}
</style>
