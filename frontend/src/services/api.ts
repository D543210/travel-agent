import axios from 'axios'
import type {
  JobCreatedResponse,
  PoiSearchItem,
  PlanningJob,
  TripDetail,
  TripEditOperation,
  TripFormData,
  TripPlanResponse,
  TripPlanningJobRequest,
  TripSummary,
  UserPreference
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10分钟超时
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    const requestUrl = String(error.config?.url || '')
    if (
      error.response?.status === 401 &&
      !requestUrl.includes('/api/auth/login') &&
      !requestUrl.includes('/api/auth/register') &&
      !requestUrl.includes('/api/auth/me')
    ) {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'))
    }
    return Promise.reject(error)
  }
)


interface AttractionPhotoResponse{
  success: boolean
  message: string
  data?:{
    name: string
    photo_url: string | null
  }
}


export async function getAttractionPhoto(
  name: string
): Promise<string | null>{
  try{
    const response =
      await apiClient.get<AttractionPhotoResponse>(
        '/api/poi/photo',
        {
          params:{
            name
          }
        }
      )
      return response.data.data?.photo_url || null
  }catch(error){
    console.error(`获取${name}图片失败:`, error)
    return null
  }
}

/**
 * 生成旅行计划
 */
export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  } catch (error: any) {
    console.error('生成旅行计划失败:', error)
    const detail = error.response?.data?.detail

    const message =
      typeof detail === 'string'? detail: detail?.message || error.message || '生成旅行计划失败'

    throw new Error(message)
  }
}

export async function createTripPlanningJob(
  formData: TripPlanningJobRequest
): Promise<JobCreatedResponse> {
  const response = await apiClient.post<JobCreatedResponse>('/api/trips/plan', formData)
  return response.data
}

export async function getPlanningJob(jobId: string): Promise<PlanningJob> {
  const response = await apiClient.get<PlanningJob>(`/api/jobs/${jobId}`)
  return response.data
}

export async function getTrip(tripId: string): Promise<TripDetail> {
  const response = await apiClient.get<TripDetail>(`/api/trips/${tripId}`)
  return response.data
}

export async function getTrips(includeArchived = false): Promise<TripSummary[]> {
  const response = await apiClient.get<TripSummary[]>('/api/trips', {
    params: { include_archived: includeArchived }
  })
  return response.data
}

export async function archiveTrip(tripId: string): Promise<void> {
  await apiClient.delete(`/api/trips/${tripId}`)
}

export async function restoreTrip(tripId: string): Promise<void> {
  await apiClient.post(`/api/trips/${tripId}/restore`)
}

export async function getPlanningJobs(activeOnly = true): Promise<PlanningJob[]> {
  const response = await apiClient.get<PlanningJob[]>('/api/jobs', {
    params: { active_only: activeOnly }
  })
  return response.data
}

export async function createTripRevision(
  tripId: string,
  expectedVersion: number,
  operations: TripEditOperation[]
): Promise<JobCreatedResponse> {
  const response = await apiClient.post<JobCreatedResponse>(
    `/api/trips/${tripId}/revisions`,
    { expected_version: expectedVersion, operations }
  )
  return response.data
}

export async function getPreferences(): Promise<UserPreference | null> {
  const response = await apiClient.get<UserPreference | null>('/api/preferences/me')
  return response.data
}

export async function savePreferences(preference: UserPreference): Promise<UserPreference> {
  const response = await apiClient.put<UserPreference>('/api/preferences/me', preference)
  return response.data
}

export async function deletePreferences(): Promise<void> {
  await apiClient.delete('/api/preferences/me')
}

export async function searchPois(
  keywords: string,
  city: string
): Promise<PoiSearchItem[]> {
  const response = await apiClient.get<{
    success: boolean
    data: PoiSearchItem[]
  }>('/api/poi/search', { params: { keywords, city } })
  return response.data.data || []
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

export default apiClient
