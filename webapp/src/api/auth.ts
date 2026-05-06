import { api } from './client'
import type { LoginRequest, LoginResponse, UserInfo } from '@/types/api'

export const authApi = {
  login:   (body: LoginRequest)  => api.post<LoginResponse>('/api/auth/login', body),
  googleLogin: (params: { credential?: string, access_token?: string }) => api.post<LoginResponse>('/api/auth/google', params),
  logout:  ()                    => api.post<void>('/api/auth/logout'),
  me:      ()                    => api.get<UserInfo>('/api/auth/me'),
}
