package com.example.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.data.api.ApiClient
import com.example.data.model.*
import com.example.data.repository.SafetyRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SafetyViewModel(
    private val repository: SafetyRepository = SafetyRepository()
) : ViewModel() {

    private val _currentUser = MutableStateFlow<UserProfile?>(null)
    val currentUser: StateFlow<UserProfile?> = _currentUser.asStateFlow()

    private val _incidents = MutableStateFlow<List<Incident>>(emptyList())
    val incidents: StateFlow<List<Incident>> = _incidents.asStateFlow()

    private val _currentIncident = MutableStateFlow<Incident?>(null)
    val currentIncident: StateFlow<Incident?> = _currentIncident.asStateFlow()

    private val _contacts = MutableStateFlow<List<TrustedContact>>(emptyList())
    val contacts: StateFlow<List<TrustedContact>> = _contacts.asStateFlow()

    private val _journeys = MutableStateFlow<List<ChildJourney>>(emptyList())
    val journeys: StateFlow<List<ChildJourney>> = _journeys.asStateFlow()

    private val _elderCheckIns = MutableStateFlow<List<ElderCheckIn>>(emptyList())
    val elderCheckIns: StateFlow<List<ElderCheckIn>> = _elderCheckIns.asStateFlow()

    private val _assistanceRequests = MutableStateFlow<List<AssistanceRequest>>(emptyList())
    val assistanceRequests: StateFlow<List<AssistanceRequest>> = _assistanceRequests.asStateFlow()

    private val _responderAssignments = MutableStateFlow<ResponderAssignments?>(null)
    val responderAssignments: StateFlow<ResponderAssignments?> = _responderAssignments.asStateFlow()

    private val _communityInsights = MutableStateFlow<CommunityInsights?>(null)
    val communityInsights: StateFlow<CommunityInsights?> = _communityInsights.asStateFlow()

    private val _hazards = MutableStateFlow<List<CommunityHazard>>(emptyList())
    val hazards: StateFlow<List<CommunityHazard>> = _hazards.asStateFlow()

    private val _isLoading = MutableStateFlow<Boolean>(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val _successMessage = MutableStateFlow<String?>(null)
    val successMessage: StateFlow<String?> = _successMessage.asStateFlow()

    private val _apiBaseUrl = MutableStateFlow<String>(ApiClient.baseUrl)
    val apiBaseUrl: StateFlow<String> = _apiBaseUrl.asStateFlow()

    init {
        // Find the live demo backend at start-up so a real phone works without typing an IP.
        viewModelScope.launch {
            ApiClient.resolveLiveBaseUrl()
            _apiBaseUrl.value = ApiClient.baseUrl
        }
    }

    fun updateApiBaseUrl(newUrl: String) {
        ApiClient.userOverride = true
        ApiClient.baseUrl = newUrl
        _apiBaseUrl.value = ApiClient.baseUrl
    }

    fun clearMessages() {
        _errorMessage.value = null
        _successMessage.value = null
    }

    fun login(email: String, password: String, onComplete: (Boolean) -> Unit) {
        viewModelScope.launch {
            _isLoading.value = true
            clearMessages()
            ApiClient.resolveLiveBaseUrl()
            _apiBaseUrl.value = ApiClient.baseUrl
            val result = repository.login(LoginRequest(email.trim(), password))
            result.onSuccess {
                fetchProfile()
                fetchAllData()
                _isLoading.value = false
                onComplete(true)
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message ?: "Authentication failed."
                onComplete(false)
            }
        }
    }

    fun register(
        email: String,
        password: String,
        fullName: String,
        role: String = "resident",
        phone: String? = null,
        address: String? = null,
        emergencyNotes: String? = null,
        onComplete: (Boolean) -> Unit
    ) {
        viewModelScope.launch {
            _isLoading.value = true
            clearMessages()
            val result = repository.register(
                RegisterRequest(
                    email = email.trim(),
                    password = password,
                    fullName = fullName,
                    role = role,
                    phone = phone,
                    address = address,
                    emergencyNotes = emergencyNotes
                )
            )
            result.onSuccess {
                fetchProfile()
                fetchAllData()
                _isLoading.value = false
                onComplete(true)
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message ?: "Registration failed."
                onComplete(false)
            }
        }
    }

    fun logout() {
        ApiClient.authToken = null
        _currentUser.value = null
        _incidents.value = emptyList()
        _contacts.value = emptyList()
        _journeys.value = emptyList()
        _elderCheckIns.value = emptyList()
        _assistanceRequests.value = emptyList()
        _responderAssignments.value = null
    }

    fun fetchProfile() {
        viewModelScope.launch {
            repository.getProfile().onSuccess {
                _currentUser.value = it
            }
        }
    }

    fun fetchAllData() {
        fetchIncidents()
        fetchContacts()
        fetchJourneys()
        fetchElderData()
        fetchCommunityData()
        if (_currentUser.value?.role == "responder" || _currentUser.value?.role == "admin") {
            fetchResponderAssignments()
        }
    }

    fun triggerSOS(
        lat: Double? = 12.9716,
        lng: Double? = 77.5946,
        address: String? = null,
        onSuccess: (Incident) -> Unit
    ) {
        viewModelScope.launch {
            _isLoading.value = true
            clearMessages()
            val req = SOSRequest(
                latitude = lat,
                longitude = lng,
                locationAddress = address ?: _currentUser.value?.address ?: "Current Device GPS Coordinates",
                description = "EMERGENCY SOS triggered by ${_currentUser.value?.fullName ?: "Resident"}."
            )
            val res = repository.triggerSOS(req)
            _isLoading.value = false
            res.onSuccess {
                _successMessage.value = "Emergency SOS registered: ${it.referenceCode}"
                fetchIncidents()
                onSuccess(it)
            }.onFailure {
                _errorMessage.value = it.message ?: "Failed to broadcast emergency SOS."
            }
        }
    }

    fun createIncident(
        title: String,
        description: String,
        type: String,
        priority: String,
        address: String?,
        onSuccess: (Incident) -> Unit
    ) {
        viewModelScope.launch {
            _isLoading.value = true
            clearMessages()
            val req = IncidentCreateRequest(
                title = title,
                description = description,
                incidentType = type,
                priority = priority,
                locationAddress = address
            )
            val res = repository.createIncident(req)
            _isLoading.value = false
            res.onSuccess {
                _successMessage.value = "Incident ${it.referenceCode} registered."
                fetchIncidents()
                onSuccess(it)
            }.onFailure {
                _errorMessage.value = it.message ?: "Failed to log incident."
            }
        }
    }

    fun fetchIncidents() {
        viewModelScope.launch {
            repository.getIncidents().onSuccess {
                _incidents.value = it
            }
        }
    }

    fun loadIncidentDetail(id: Int) {
        viewModelScope.launch {
            _isLoading.value = true
            repository.getIncident(id).onSuccess {
                _currentIncident.value = it
                _isLoading.value = false
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message
            }
        }
    }

    fun acknowledgeIncident(id: Int) {
        viewModelScope.launch {
            _isLoading.value = true
            repository.acknowledgeIncident(id).onSuccess {
                _currentIncident.value = it
                _isLoading.value = false
                fetchIncidents()
                fetchResponderAssignments()
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message
            }
        }
    }

    fun updateIncidentStatus(id: Int, status: String, notes: String? = null) {
        viewModelScope.launch {
            _isLoading.value = true
            repository.updateIncidentStatus(id, status, notes).onSuccess {
                _currentIncident.value = it
                _isLoading.value = false
                fetchIncidents()
                fetchResponderAssignments()
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message
            }
        }
    }

    fun fetchContacts() {
        viewModelScope.launch {
            repository.getContacts().onSuccess {
                _contacts.value = it
            }
        }
    }

    fun addContact(name: String, relationship: String, phone: String, email: String?) {
        viewModelScope.launch {
            _isLoading.value = true
            repository.addContact(CreateContactRequest(name, relationship, phone, email)).onSuccess {
                _isLoading.value = false
                fetchContacts()
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message
            }
        }
    }

    fun deleteContact(id: Int) {
        viewModelScope.launch {
            repository.deleteContact(id).onSuccess {
                fetchContacts()
            }
        }
    }

    fun fetchJourneys() {
        viewModelScope.launch {
            repository.getChildJourneys().onSuccess {
                _journeys.value = it
            }
        }
    }

    fun createJourney(name: String, origin: String, destination: String, duration: Int, notes: String?) {
        viewModelScope.launch {
            _isLoading.value = true
            repository.createChildJourney(CreateJourneyRequest(name, origin, destination, duration, notes)).onSuccess {
                _isLoading.value = false
                fetchJourneys()
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message
            }
        }
    }

    fun checkInJourney(id: Int, status: String) {
        viewModelScope.launch {
            repository.checkInChildJourney(id, status).onSuccess {
                fetchJourneys()
            }
        }
    }

    fun fetchElderData() {
        viewModelScope.launch {
            repository.getElderCheckIns().onSuccess {
                _elderCheckIns.value = it
            }
            repository.getAssistanceRequests().onSuccess {
                _assistanceRequests.value = it
            }
        }
    }

    fun submitElderCheckIn(wellness: String) {
        viewModelScope.launch {
            repository.submitElderCheckIn(wellness).onSuccess {
                fetchElderData()
            }
        }
    }

    fun createAssistanceRequest(type: String, description: String, urgency: String) {
        viewModelScope.launch {
            repository.createAssistanceRequest(CreateAssistanceRequest(type, description, urgency)).onSuccess {
                fetchElderData()
            }
        }
    }

    fun fetchResponderAssignments() {
        viewModelScope.launch {
            repository.getResponderAssignments().onSuccess {
                _responderAssignments.value = it
            }
        }
    }

    fun toggleAvailability(isAvailable: Boolean) {
        viewModelScope.launch {
            repository.updateAvailability(isAvailable).onSuccess {
                fetchResponderAssignments()
            }
        }
    }

    fun fetchCommunityData() {
        viewModelScope.launch {
            repository.getCommunityInsights().onSuccess {
                _communityInsights.value = it
            }
            repository.getHazards().onSuccess {
                _hazards.value = it
            }
        }
    }

    fun reportHazard(title: String, type: String, severity: String, address: String) {
        viewModelScope.launch {
            _isLoading.value = true
            repository.reportHazard(CreateHazardRequest(title, type, severity, address)).onSuccess {
                _isLoading.value = false
                fetchCommunityData()
            }.onFailure {
                _isLoading.value = false
                _errorMessage.value = it.message
            }
        }
    }
}
