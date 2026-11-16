package com.example.data.api

import com.example.data.model.*
import retrofit2.Response
import retrofit2.http.*

interface SafetyApiService {

    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequest): Response<AuthResponse>

    @POST("api/v1/auth/register")
    suspend fun register(@Body body: RegisterRequest): Response<AuthResponse>

    @GET("api/v1/profiles/me")
    suspend fun getProfile(@Header("Authorization") auth: String): Response<UserProfile>

    @GET("api/v1/trusted-contacts")
    suspend fun getContacts(@Header("Authorization") auth: String): Response<List<TrustedContact>>

    @POST("api/v1/trusted-contacts")
    suspend fun addContact(
        @Header("Authorization") auth: String,
        @Body body: CreateContactRequest
    ): Response<TrustedContact>

    @DELETE("api/v1/trusted-contacts/{id}")
    suspend fun deleteContact(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): Response<Unit>

    @POST("api/v1/sos")
    suspend fun triggerSOS(
        @Header("Authorization") auth: String,
        @Body body: SOSRequest
    ): Response<Incident>

    @POST("api/v1/incidents")
    suspend fun createIncident(
        @Header("Authorization") auth: String,
        @Body body: IncidentCreateRequest
    ): Response<Incident>

    @GET("api/v1/incidents")
    suspend fun getIncidents(
        @Header("Authorization") auth: String,
        @Query("status") status: String? = null,
        @Query("type") type: String? = null
    ): Response<List<Incident>>

    @GET("api/v1/incidents/{id}")
    suspend fun getIncident(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): Response<Incident>

    @POST("api/v1/incidents/{id}/acknowledge")
    suspend fun acknowledgeIncident(
        @Header("Authorization") auth: String,
        @Path("id") id: Int
    ): Response<Incident>

    @POST("api/v1/incidents/{id}/status")
    suspend fun updateIncidentStatus(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: IncidentStatusUpdateRequest
    ): Response<Incident>

    @GET("api/v1/children/journeys")
    suspend fun getChildJourneys(@Header("Authorization") auth: String): Response<List<ChildJourney>>

    @POST("api/v1/children/journeys")
    suspend fun createChildJourney(
        @Header("Authorization") auth: String,
        @Body body: CreateJourneyRequest
    ): Response<ChildJourney>

    @POST("api/v1/children/journeys/{id}/check-in")
    suspend fun checkInChildJourney(
        @Header("Authorization") auth: String,
        @Path("id") id: Int,
        @Body body: ChildCheckInRequest
    ): Response<ChildJourney>

    @GET("api/v1/elder-care/checkins")
    suspend fun getElderCheckIns(@Header("Authorization") auth: String): Response<List<ElderCheckIn>>

    @POST("api/v1/elder-care/checkins")
    suspend fun submitElderCheckIn(
        @Header("Authorization") auth: String,
        @Body body: CreateElderCheckInRequest
    ): Response<ElderCheckIn>

    @GET("api/v1/elder-care/assistance-requests")
    suspend fun getAssistanceRequests(@Header("Authorization") auth: String): Response<List<AssistanceRequest>>

    @POST("api/v1/elder-care/assistance-requests")
    suspend fun createAssistanceRequest(
        @Header("Authorization") auth: String,
        @Body body: CreateAssistanceRequest
    ): Response<AssistanceRequest>

    @GET("api/v1/responders/assignments")
    suspend fun getResponderAssignments(@Header("Authorization") auth: String): Response<ResponderAssignments>

    @PATCH("api/v1/responders/availability")
    suspend fun updateAvailability(
        @Header("Authorization") auth: String,
        @Body body: UpdateAvailabilityRequest
    ): Response<Map<String, Any>>

    @GET("api/v1/community/insights")
    suspend fun getCommunityInsights(@Header("Authorization") auth: String): Response<CommunityInsights>

    @GET("api/v1/community/hazards")
    suspend fun getHazards(@Header("Authorization") auth: String): Response<List<CommunityHazard>>

    @POST("api/v1/community/hazards")
    suspend fun reportHazard(
        @Header("Authorization") auth: String,
        @Body body: CreateHazardRequest
    ): Response<CommunityHazard>
}
