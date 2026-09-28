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
  ticket_price?: number
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
