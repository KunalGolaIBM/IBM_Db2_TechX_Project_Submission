import { 
  AuthResponse, User, TrustedContact, Incident, ChildJourney, 
  ElderCheckIn, AssistanceRequest, CommunityInsights, CommunityHazard, 
  AIAnalysisResult, SimilarIncident } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class ApiService {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('nsin_auth_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('nsin_auth_token', token);
    } else {
      localStorage.removeItem('nsin_auth_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 204) {
        return null as unknown as T;
      }

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Request failed with status ${response.status}`);
      }

      return data as T;
    } catch (err: any) {
      console.error(`API Error on [${options.method || 'GET'} ${endpoint}]:`, err);
      throw err;
    }
  }

  // --- Health ---
  async getSystemHealth(): Promise<any> {
    return this.request('/health');
  }

  // --- Auth ---
  async login(credentials: { email: string; password: string }): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    this.setToken(res.access_token);
    return res;
  }

  async register(userData: any): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
    this.setToken(res.access_token);
    return res;
  }

  async getProfile(): Promise<User> {
    return this.request<User>('/api/v1/profiles/me');
  }

  async updateProfile(updates: Partial<User>): Promise<User> {
    return this.request<User>('/api/v1/profiles/me', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  // --- Trusted Contacts ---
  async getContacts(): Promise<TrustedContact[]> {
    return this.request<TrustedContact[]>('/api/v1/trusted-contacts');
  }

  async addContact(contact: { name: string; relationship: string; phone: string; email?: string }): Promise<TrustedContact> {
    return this.request<TrustedContact>('/api/v1/trusted-contacts', {
      method: 'POST',
      body: JSON.stringify(contact),
    });
  }

  async deleteContact(contactId: number): Promise<void> {
    return this.request<void>(`/api/v1/trusted-contacts/${contactId}`, {
      method: 'DELETE',
    });
  }

  // --- Emergency SOS & Incidents ---
  async triggerSOS(data: { latitude?: number; longitude?: number; location_address?: string; description?: string }): Promise<Incident> {
    return this.request<Incident>('/api/v1/sos', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async createIncident(incident: { title: string; description: string; incident_type: string; priority?: string; location_address?: string }): Promise<Incident> {
    return this.request<Incident>('/api/v1/incidents', {
      method: 'POST',
      body: JSON.stringify(incident),
    });
  }

  async getIncidents(filters?: { status?: string; type?: string }): Promise<Incident[]> {
    const params = new URLSearchParams();
    if (filters?.status) params.append('status', filters.status);
    if (filters?.type) params.append('type', filters.type);
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request<Incident[]>(`/api/v1/incidents${query}`);
  }

  async getIncident(id: number): Promise<Incident> {
    return this.request<Incident>(`/api/v1/incidents/${id}`);
  }

  async getSimilarIncidents(id: number): Promise<SimilarIncident[]> {
    return this.request<SimilarIncident[]>(`/api/v1/incidents/${id}/similar`);
  }

  async acknowledgeIncident(id: number): Promise<Incident> {
    return this.request<Incident>(`/api/v1/incidents/${id}/acknowledge`, {
      method: 'POST',
    });
  }

  async updateIncidentStatus(id: number, status: string, notes?: string): Promise<Incident> {
    return this.request<Incident>(`/api/v1/incidents/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status, notes }),
    });
  }

  // --- Child Safety ---
  async getChildJourneys(): Promise<ChildJourney[]> {
    return this.request<ChildJourney[]>('/api/v1/children/journeys');
  }

  async createChildJourney(data: { child_name: string; origin: string; destination: string; expected_duration_minutes: number; notes?: string }): Promise<ChildJourney> {
    return this.request<ChildJourney>('/api/v1/children/journeys', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async checkInChildJourney(journeyId: number, checkInData: { status: string; notes?: string }): Promise<ChildJourney> {
    return this.request<ChildJourney>(`/api/v1/children/journeys/${journeyId}/check-in`, {
      method: 'POST',
      body: JSON.stringify(checkInData),
    });
  }

  // --- Elder Care ---
  async getElderCheckIns(): Promise<ElderCheckIn[]> {
    return this.request<ElderCheckIn[]>('/api/v1/elder-care/checkins');
  }

  async submitElderCheckIn(data: { wellness_status: string; notes?: string }): Promise<ElderCheckIn> {
    return this.request<ElderCheckIn>('/api/v1/elder-care/checkins', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getAssistanceRequests(): Promise<AssistanceRequest[]> {
    return this.request<AssistanceRequest[]>('/api/v1/elder-care/assistance-requests');
  }

  async createAssistanceRequest(data: { request_type: string; description: string; urgency: string }): Promise<AssistanceRequest> {
    return this.request<AssistanceRequest>('/api/v1/elder-care/assistance-requests', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // --- Responders ---
  async getResponderAssignments(): Promise<{ responder_name: string; is_available: boolean; incidents: Incident[]; assistance_requests: AssistanceRequest[] }> {
    return this.request('/api/v1/responders/assignments');
  }

  async updateAvailability(is_available: boolean, lat?: number, lng?: number): Promise<any> {
    return this.request('/api/v1/responders/availability', {
      method: 'PATCH',
      body: JSON.stringify({ is_available, current_lat: lat, current_lng: lng }),
    });
  }

  async getResponderRoster(): Promise<any[]> {
    return this.request('/api/v1/responders/roster');
  }

  // --- Community Insights & Hazards ---
  async getCommunityInsights(): Promise<CommunityInsights> {
    return this.request<CommunityInsights>('/api/v1/community/insights');
  }

  async getHazards(): Promise<CommunityHazard[]> {
    return this.request<CommunityHazard[]>('/api/v1/community/hazards');
  }

  async reportHazard(hazard: { title: string; hazard_type: string; severity: string; address: string }): Promise<CommunityHazard> {
    return this.request<CommunityHazard>('/api/v1/community/hazards', {
      method: 'POST',
      body: JSON.stringify(hazard),
    });
  }

  // --- AI Intelligence ---
  async getIncidentAIAssistance(raw_text: string, incident_type?: string, location?: string, incident_id?: number): Promise<AIAnalysisResult> {
    return this.request<AIAnalysisResult>('/api/v1/ai/incident-assistance', {
      method: 'POST',
      body: JSON.stringify({ raw_text, incident_type, location_address: location, incident_id }),
    });
  }

  async getSafetyGuidance(query: string, category?: string): Promise<any> {
    const params = new URLSearchParams({ query });
    if (category) params.append('category', category);
    return this.request(`/api/v1/ai/guidance?${params.toString()}`);
  }
}

export const api = new ApiService();
