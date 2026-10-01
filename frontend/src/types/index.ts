// 类型定义

export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  poi_id?: string
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  ticket_price?: number | null
}

export interface Meal {
  poi_id: string
  type: 'breakfast' | 'lunch' | 'dinner'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

export interface TravelLeg {
  origin_poi_id: string
  origin_name: string
  destination_poi_id: string
  destination_name: string
  distance: number
  duration: number
  route_type: 'walking' | 'driving' | 'transit'
  description: string
}

export interface Hotel {
  poi_id: string
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
  travel_legs: TravelLeg[]
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
  status: 'success' | 'degraded'
  warnings: string[]
}

export interface TripFormData {
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
}

export interface TripPlanResponse {
  success: boolean
  status: 'success' | 'degraded' | 'failed'
  message: string
  warnings: string[]
  data?: TripPlan
}

export interface AuthUser {
  id: string
  email: string
  display_name: string
  is_active: boolean
  created_at: string
}

export interface AuthResponse {
  message: string
  user: AuthUser
}

export interface TripPlanningJobRequest extends TripFormData {
  use_saved_preferences: boolean
}

export interface JobCreatedResponse {
  job_id: string
  trip_id: string
  status: 'queued'
}

export interface PlanningJob {
  job_id: string
  trip_id: string
  kind: 'generate_trip' | 'revise_trip'
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  stage: string
  progress_current: number
  progress_total: number
  progress_percent: number
  progress_message: string
  result_version?: number
  error_code?: string
  error_message?: string
  attempts: number
}

export interface TripDetail {
  trip_id: string
  version: number
  status: string
  plan: TripPlan
}

export interface TripSummary {
  trip_id: string
  title: string
  status: 'planning' | 'ready' | 'failed'
  current_version: number
  created_at: string
  updated_at: string
  archived_at?: string | null
}

export interface UserPreference {
  attraction_types: string[]
  dietary_restrictions: string[]
  travel_pace?: string | null
  transportation_preference?: string | null
  accommodation_preference?: string | null
  version?: number
  updated_at?: string
}

export interface PoiSearchItem {
  id: string
  name: string
  type: string
  address: string
  location: Location
  tel?: string | null
}

export interface TripEditOperation {
  type: 'delete_attraction' | 'move_attraction' | 'update_visit_duration' | 'replace_attraction'
  day_index: number
  attraction_index: number
  target_index?: number
  visit_duration?: number
  replacement_poi_id?: string
}
