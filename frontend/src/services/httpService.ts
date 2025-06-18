import axios, { 
  AxiosInstance, 
  AxiosRequestConfig, 
  AxiosResponse, 
  AxiosError,
  InternalAxiosRequestConfig
} from 'axios';
import API_BASE_URL, { TOKEN_KEY } from '../config';

// Debug flag
const DEBUG = true;

const httpClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest' // Penting untuk CORS
  },
  withCredentials: false // Set false untuk koneksi cross-origin sederhana
});

// Interceptor untuk menambahkan token ke request
httpClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    console.log(`[HTTP] Request ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, config.data);
    
    // Handling untuk multipart/form-data
    if (config.data instanceof FormData) {
      // Hapus Content-Type agar browser mengatur boundary yang benar
      delete config.headers['Content-Type'];
    }
    
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError): Promise<AxiosError> => {
    console.error('[HTTP] Request Error:', error);
    return Promise.reject(error);
  }
);

// Interceptor untuk handling error response
httpClient.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => {
    console.log(`[HTTP] Response ${response.status} from ${response.config.url}`, response.data);
    return response;
  },
  (error: AxiosError): Promise<AxiosError> => {
    console.error('[HTTP] Response Error:', error);
    if (error.response) {
      console.error(`[HTTP] Error ${error.response.status}:`, error.response.data);
    }
    
    // Log CORS errors
    if (!error.response) {
      console.error('This might be a CORS issue. Check network tab for details.');
    }
    
    const { response: errorResponse } = error;
    const status = errorResponse?.status;
    
    if (status === 401) {
      console.warn('[HTTP] Unauthorized - Token might be expired');
      localStorage.removeItem(TOKEN_KEY);
      // Redirect ke login jika di-uncomment
      // window.location.href = '/login';
    }
    
    return Promise.reject(error);
  }
);

// Khusus untuk permintaan multipart/form-data (upload file)
const uploadFile = <T = any>(url: string, formData: FormData, config: AxiosRequestConfig = {}): Promise<AxiosResponse<T>> => {
  // Jangan set Content-Type secara manual, biarkan browser membuat boundary yang benar
  return httpClient.post<T>(url, formData, {
    ...config,
    headers: {
      ...config.headers,
      // Jangan set 'Content-Type': 'multipart/form-data' di sini
      // Browser akan mengatur boundary yang benar secara otomatis
    }
  });
};

// Tambahkan fungsi logging khusus untuk metode PUT
const enhancedPut = <T = any>(url: string, data?: any, conf?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
  console.log('[HTTP-PUT] Request URL:', url);
  console.log('[HTTP-PUT] Request Data:', data);
  console.log('[HTTP-PUT] Request Config:', conf);
  
  return httpClient.put<T>(url, data, conf)
    .then(response => {
      console.log('[HTTP-PUT] Response Status:', response.status);
      console.log('[HTTP-PUT] Response Headers:', response.headers);
      console.log('[HTTP-PUT] Response Data:', response.data);
      return response;
    })
    .catch(error => {
      console.error('[HTTP-PUT] Error:', error);
      if (error.response) {
        console.error('[HTTP-PUT] Error Response:', {
          status: error.response.status,
          statusText: error.response.statusText,
          headers: error.response.headers,
          data: error.response.data
        });
      }
      throw error;
    });
};

// Tambahkan fungsi logging khusus untuk metode POST
const enhancedPost = <T = any>(url: string, data?: any, conf?: AxiosRequestConfig): Promise<AxiosResponse<T>> => {
  console.log('[HTTP-POST] Request URL:', url);
  console.log('[HTTP-POST] Request Data:', data);
  console.log('[HTTP-POST] Request Config:', conf);
  
  return httpClient.post<T>(url, data, conf)
    .then(response => {
      console.log('[HTTP-POST] Response Status:', response.status);
      console.log('[HTTP-POST] Response Headers:', response.headers);
      console.log('[HTTP-POST] Response Data:', response.data);
      return response;
    })
    .catch(error => {
      console.error('[HTTP-POST] Error:', error);
      if (error.response) {
        console.error('[HTTP-POST] Error Response:', {
          status: error.response.status,
          statusText: error.response.statusText,
          headers: error.response.headers,
          data: error.response.data
        });
      }
      throw error;
    });
};

// Perbarui objek ekspor untuk menggunakan enhancedPut
export default {
  get: <T = any>(url: string, conf?: AxiosRequestConfig): Promise<AxiosResponse<T>> => 
    httpClient.get<T>(url, conf),
  post: enhancedPost,
  put: enhancedPut,
  delete: <T = any>(url: string, conf?: AxiosRequestConfig): Promise<AxiosResponse<T>> => 
    httpClient.delete<T>(url, conf),
  upload: uploadFile
};

// Helper untuk format API error
export const formatApiError = (error: any): string => {
  if (!error.response) {
    // Network error atau tidak ada respon
    return 'Tidak dapat terhubung ke server. Periksa koneksi Anda atau coba lagi nanti.';
  }
  
  const { status, data } = error.response;
  
  // Format error berdasarkan status code
  switch (status) {
    case 400:
      if (typeof data === 'string') return data;
      if (data.detail) return data.detail;
      return 'Permintaan tidak valid. Periksa kembali data yang dimasukkan.';
    
    case 401:
      return 'Sesi telah berakhir. Silakan login kembali.';
    
    case 403:
      return 'Anda tidak memiliki akses untuk melakukan tindakan ini.';
    
    case 404:
      return 'Data yang diminta tidak ditemukan.';
    
    case 422:
      // Validation error dari FastAPI
      if (data.detail && Array.isArray(data.detail)) {
        return data.detail.map((err: any) => 
          `${err.loc ? err.loc.slice(1).join('.') + ': ' : ''}${err.msg}`
        ).join('\n');
      }
      return data.detail || 'Validasi data gagal. Periksa kembali input Anda.';
    
    case 500:
      return 'Terjadi kesalahan pada server. Mohon coba lagi nanti.';
    
    default:
      return data.detail || `Terjadi kesalahan (${status}).`;
  }
};