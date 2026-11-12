package com.example.data.repository

import com.example.data.api.ApiClient
import com.example.data.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class SafetyRepository {

    private val api get() = ApiClient.getService()
    private val authHeader get() = ApiClient.getAuthHeader()

    suspend fun login(req: LoginRequest): Result<AuthResponse> = withContext(Dispatchers.IO) {
        try {
            val response = api.login(req)
            if (response.isSuccessful && response.body() != null) {
                val body = response.body()!!
                ApiClient.authToken = body.accessToken
                Result.success(body)
            } else {
                val errorMsg = response.errorBody()?.string() ?: "Login failed with code ${response.code()}"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun register(req: RegisterRequest): Result<AuthResponse> = withContext(Dispatchers.IO) {
        try {
            val response = api.register(req)
            if (response.isSuccessful && response.body() != null) {
                val body = response.body()!!
                ApiClient.authToken = body.accessToken
                Result.success(body)
            } else {
                val errorMsg = response.errorBody()?.string() ?: "Registration failed with code ${response.code()}"
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getProfile(): Result<UserProfile> = withContext(Dispatchers.IO) {
        try {
            val response = api.getProfile(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch profile"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun triggerSOS(req: SOSRequest): Result<Incident> = withContext(Dispatchers.IO) {
        try {
            val response = api.triggerSOS(authHeader, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception(response.errorBody()?.string() ?: "SOS trigger failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createIncident(req: IncidentCreateRequest): Result<Incident> = withContext(Dispatchers.IO) {
        try {
            val response = api.createIncident(authHeader, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception(response.errorBody()?.string() ?: "Incident creation failed"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getIncidents(status: String? = null): Result<List<Incident>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getIncidents(authHeader, status = status)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch incidents"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getIncident(id: Int): Result<Incident> = withContext(Dispatchers.IO) {
        try {
            val response = api.getIncident(authHeader, id)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to load incident detail"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun acknowledgeIncident(id: Int): Result<Incident> = withContext(Dispatchers.IO) {
        try {
            val response = api.acknowledgeIncident(authHeader, id)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to acknowledge incident"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateIncidentStatus(id: Int, status: String, notes: String? = null): Result<Incident> = withContext(Dispatchers.IO) {
        try {
            val response = api.updateIncidentStatus(authHeader, id, IncidentStatusUpdateRequest(status, notes))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to update status"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getContacts(): Result<List<TrustedContact>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getContacts(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch contacts"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun addContact(req: CreateContactRequest): Result<TrustedContact> = withContext(Dispatchers.IO) {
        try {
            val response = api.addContact(authHeader, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to add contact"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteContact(id: Int): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = api.deleteContact(authHeader, id)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to delete contact"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getChildJourneys(): Result<List<ChildJourney>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getChildJourneys(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch journeys"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createChildJourney(req: CreateJourneyRequest): Result<ChildJourney> = withContext(Dispatchers.IO) {
        try {
            val response = api.createChildJourney(authHeader, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to create journey"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun checkInChildJourney(id: Int, status: String, notes: String? = null): Result<ChildJourney> = withContext(Dispatchers.IO) {
        try {
            val response = api.checkInChildJourney(authHeader, id, ChildCheckInRequest(status, notes))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed check-in"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getElderCheckIns(): Result<List<ElderCheckIn>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getElderCheckIns(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to load elder check-ins"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun submitElderCheckIn(wellness: String, notes: String? = null): Result<ElderCheckIn> = withContext(Dispatchers.IO) {
        try {
            val response = api.submitElderCheckIn(authHeader, CreateElderCheckInRequest(wellness, notes))
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed elder check-in"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getAssistanceRequests(): Result<List<AssistanceRequest>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getAssistanceRequests(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to fetch assistance requests"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun createAssistanceRequest(req: CreateAssistanceRequest): Result<AssistanceRequest> = withContext(Dispatchers.IO) {
        try {
            val response = api.createAssistanceRequest(authHeader, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to create assistance request"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getResponderAssignments(): Result<ResponderAssignments> = withContext(Dispatchers.IO) {
        try {
            val response = api.getResponderAssignments(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to load responder assignments"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateAvailability(isAvailable: Boolean): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = api.updateAvailability(authHeader, UpdateAvailabilityRequest(isAvailable))
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to update availability"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getCommunityInsights(): Result<CommunityInsights> = withContext(Dispatchers.IO) {
        try {
            val response = api.getCommunityInsights(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to load community insights"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getHazards(): Result<List<CommunityHazard>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getHazards(authHeader)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to load hazards"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun reportHazard(req: CreateHazardRequest): Result<CommunityHazard> = withContext(Dispatchers.IO) {
        try {
            val response = api.reportHazard(authHeader, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("Failed to report hazard"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
