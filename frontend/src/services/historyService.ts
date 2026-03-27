import httpService from './httpService';
import { HistoryEventListResponse, EventType } from '../types/history';

const API_URL = '/api/v1/history';

export const historyService = {
  async getHistory(
    page: number = 1, 
    limit: number = 10,
    eventType?: EventType,
    startDate?: string,
    endDate?: string
  ): Promise<HistoryEventListResponse> {
    const params = new URLSearchParams({
      offset: ((page - 1) * limit).toString(),
      limit: limit.toString(),
    });

    if (eventType) {
      params.append('event_type', eventType);
    }
    if (startDate) {
      params.append('start_date', startDate);
    }
    if (endDate) {
      params.append('end_date', endDate);
    }

    const response = await httpService.get(`${API_URL}?${params.toString()}`);
    return response.data;
  },
};
