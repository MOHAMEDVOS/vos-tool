import { api } from './client'
import type { LoginRequest, LoginResponse, UserInfo } from '@/types/api'

export const authApi = {
  login:   (body: LoginRequest)  => api.post<LoginResponse>('/api/auth/login', body),
  googleLogin: (credential: string) => api.post<LoginResponse>('/api/auth/google', { credential }),
  logout:  ()                    => api.post<void>('/api/auth/logout'),
  me:      ()                    => api.get<UserInfo>('/api/auth/me'),
}
