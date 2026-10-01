import { reactive } from 'vue'
import type { AuthUser } from '@/types'
import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
  type LoginPayload,
  type RegisterPayload
} from '@/services/auth'

export const authState = reactive<{
  user: AuthUser | null
  initialized: boolean
}>({
  user: null,
  initialized: false
})

export async function initializeAuth(): Promise<void> {
  if (authState.initialized) return

  try {
    authState.user = await getCurrentUser()
  } catch {
    authState.user = null
  } finally {
    authState.initialized = true
  }
}

export async function login(payload: LoginPayload): Promise<void> {
  const response = await loginUser(payload)
  authState.user = response.user
  authState.initialized = true
}

export async function register(payload: RegisterPayload): Promise<void> {
  await registerUser(payload)
}

export async function logout(): Promise<void> {
  try {
    await logoutUser()
  } finally {
    authState.user = null
    authState.initialized = true
  }
}

export function clearAuth(): void {
  authState.user = null
  authState.initialized = true
}
