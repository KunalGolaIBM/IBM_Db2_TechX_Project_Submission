package com.example.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class LoginRequest(
    val email: String,
    val password: String
)

@JsonClass(generateAdapter = true)
data class RegisterRequest(
    val email: String,
    val password: String,
    @Json(name = "full_name") val fullName: String,
    val phone: String? = null,
    val role: String = "resident",
    val address: String? = null,
    @Json(name = "emergency_notes") val emergencyNotes: String? = null
)

@JsonClass(generateAdapter = true)
data class AuthResponse(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "token_type") val tokenType: String,
    @Json(name = "user_id") val userId: Int,
    val email: String,
    @Json(name = "full_name") val fullName: String,
    val role: String
)

@JsonClass(generateAdapter = true)
data class UserProfile(
    val id: Int,
    val email: String,
    @Json(name = "full_name") val fullName: String,
    val phone: String? = null,
    val role: String,
    @Json(name = "is_active") val isActive: Boolean = true,
    @Json(name = "is_verified") val isVerified: Boolean = false,
    @Json(name = "emergency_notes") val emergencyNotes: String? = null,
    val address: String? = null,
    @Json(name = "created_at") val createdAt: String? = null
)

@JsonClass(generateAdapter = true)
data class TrustedContact(
    val id: Int = 0,
    @Json(name = "user_id") val userId: Int = 0,
    val name: String,
    val relationship: String,
    val phone: String,
    val email: String? = null,
    @Json(name = "can_receive_sos") val canReceiveSos: Boolean = true,
    @Json(name = "can_track_location") val canTrackLocation: Boolean = true,
    @Json(name = "created_at") val createdAt: String? = null
)

@JsonClass(generateAdapter = true)
data class CreateContactRequest(
    val name: String,
    val relationship: String,
    val phone: String,
    val email: String? = null,
    @Json(name = "can_receive_sos") val canReceiveSos: Boolean = true,
    @Json(name = "can_track_location") val canTrackLocation: Boolean = true
)

@JsonClass(generateAdapter = true)
data class SOSRequest(
    val latitude: Double? = null,
    val longitude: Double? = null,
    @Json(name = "location_address") val locationAddress: String? = null,
    val description: String? = null,
    @Json(name = "emergency_type") val emergencyType: String = "sos"
)

@JsonClass(generateAdapter = true)
data class IncidentCreateRequest(
    val title: String,
    val description: String,
    @Json(name = "incident_type") val incidentType: String = "hazard",
    val priority: String = "P2_HIGH",
    @Json(name = "location_address") val locationAddress: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null
)

@JsonClass(generateAdapter = true)
data class IncidentStatusUpdateRequest(
    val status: String,
    val notes: String? = null
)

@JsonClass(generateAdapter = true)
data class IncidentStatusHistoryItem(
    val id: Int = 0,
    val status: String,
    val notes: String? = null,
    @Json(name = "updated_by_name") val updatedByName: String? = null,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class Incident(
    val id: Int,
    @Json(name = "reference_code") val referenceCode: String,
    @Json(name = "reporter_id") val reporterId: Int,
    @Json(name = "reporter_name") val reporterName: String? = null,
    val title: String,
    val description: String,
    @Json(name = "incident_type") val incidentType: String,
    val priority: String,
    val status: String,
    @Json(name = "location_address") val locationAddress: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @Json(name = "assigned_responder_id") val assignedResponderId: Int? = null,
    @Json(name = "assigned_responder_name") val assignedResponderName: String? = null,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "updated_at") val updatedAt: String,
    @Json(name = "resolved_at") val resolvedAt: String? = null,
    @Json(name = "status_history") val statusHistory: List<IncidentStatusHistoryItem> = emptyList()
)

@JsonClass(generateAdapter = true)
data class ChildJourney(
    val id: Int,
    @Json(name = "guardian_id") val guardianId: Int,
    @Json(name = "child_name") val childName: String,
    val origin: String,
    val destination: String,
    @Json(name = "expected_arrival_time") val expectedArrivalTime: String,
    @Json(name = "actual_arrival_time") val actualArrivalTime: String? = null,
    val status: String,
    @Json(name = "last_check_in") val lastCheckIn: String? = null,
    val notes: String? = null,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class CreateJourneyRequest(
    @Json(name = "child_name") val childName: String,
    val origin: String,
    val destination: String,
    @Json(name = "expected_duration_minutes") val expectedDurationMinutes: Int = 30,
    val notes: String? = null
)

@JsonClass(generateAdapter = true)
data class ChildCheckInRequest(
    val status: String = "completed",
    val notes: String? = null
)

@JsonClass(generateAdapter = true)
data class ElderCheckIn(
    val id: Int,
    @Json(name = "user_id") val userId: Int,
    @Json(name = "user_name") val userName: String? = null,
    @Json(name = "scheduled_time") val scheduledTime: String,
    @Json(name = "checked_in_at") val checkedInAt: String? = null,
    val status: String,
    @Json(name = "wellness_status") val wellnessStatus: String,
    val notes: String? = null,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class CreateElderCheckInRequest(
    @Json(name = "wellness_status") val wellnessStatus: String = "good",
    val notes: String? = null
)

@JsonClass(generateAdapter = true)
data class AssistanceRequest(
    val id: Int,
    @Json(name = "user_id") val userId: Int,
    @Json(name = "user_name") val userName: String? = null,
    @Json(name = "request_type") val requestType: String,
    val description: String,
    val urgency: String,
    val status: String,
    @Json(name = "assigned_to_name") val assignedToName: String? = null,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "resolved_at") val resolvedAt: String? = null
)

@JsonClass(generateAdapter = true)
data class CreateAssistanceRequest(
    @Json(name = "request_type") val requestType: String,
    val description: String,
    val urgency: String = "medium"
)

@JsonClass(generateAdapter = true)
data class CommunityHazard(
    val id: Int,
    @Json(name = "reported_by_id") val reportedById: Int,
    val title: String,
    @Json(name = "hazard_type") val hazardType: String,
    val severity: String,
    val address: String,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val status: String,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class CreateHazardRequest(
    val title: String,
    @Json(name = "hazard_type") val hazardType: String,
    val severity: String = "medium",
    val address: String,
    val latitude: Double? = null,
    val longitude: Double? = null
)

@JsonClass(generateAdapter = true)
data class CommunityInsights(
    @Json(name = "total_incidents") val totalIncidents: Int,
    @Json(name = "active_incidents") val activeIncidents: Int,
    @Json(name = "resolved_incidents") val resolvedIncidents: Int,
    @Json(name = "average_response_time_minutes") val averageResponseTimeMinutes: Double,
    @Json(name = "incidents_by_type") val incidentsByType: Map<String, Int> = emptyMap(),
    @Json(name = "incidents_by_priority") val incidentsByPriority: Map<String, Int> = emptyMap(),
    @Json(name = "active_hazards") val activeHazards: List<CommunityHazard> = emptyList(),
    @Json(name = "safety_health_score") val safetyHealthScore: Int = 90,
    @Json(name = "ai_safety_advisory") val aiSafetyAdvisory: String
)

@JsonClass(generateAdapter = true)
data class ResponderAssignments(
    @Json(name = "responder_name") val responderName: String,
    @Json(name = "is_available") val isAvailable: Boolean,
    val incidents: List<Incident> = emptyList(),
    @Json(name = "assistance_requests") val assistanceRequests: List<AssistanceRequest> = emptyList()
)

@JsonClass(generateAdapter = true)
data class UpdateAvailabilityRequest(
    @Json(name = "is_available") val isAvailable: Boolean,
    @Json(name = "current_lat") val currentLat: Double? = null,
    @Json(name = "current_lng") val currentLng: Double? = null
)
