import apiClient from './api'
import type { AuthResponse, AuthUser } from '@/types'

export interface RegisterPayload {
  email: string
  password: string
  display_name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export async function registerUser(payload: RegisterPayload): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/api/auth/register', payload)
  return response.data
}

export async function loginUser(payload: LoginPayload): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/api/auth/login', payload)
  return response.data
}

export async function logoutUser(): Promise<void> {
  await apiClient.post('/api/auth/logout')
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await apiClient.get<AuthUser>('/api/auth/me')
  return response.data
}
