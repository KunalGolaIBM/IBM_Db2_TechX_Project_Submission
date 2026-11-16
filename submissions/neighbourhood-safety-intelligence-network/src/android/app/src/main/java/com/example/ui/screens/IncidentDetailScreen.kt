package com.example.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.IncidentStatusHistoryItem
import com.example.ui.theme.CivicNavy
import com.example.ui.theme.CivicTeal
import com.example.ui.theme.EmergencyRed
import com.example.ui.viewmodel.SafetyViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IncidentDetailScreen(
    incidentId: Int,
    viewModel: SafetyViewModel,
    onBack: () -> Unit
) {
    val incident by viewModel.currentIncident.collectAsState()
    val currentUser by viewModel.currentUser.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    var statusNoteInput by remember { mutableStateOf("") }

    LaunchedEffect(incidentId) {
        viewModel.loadIncidentDetail(incidentId)
    }

    val isResponderOrAdmin = currentUser?.role == "responder" || currentUser?.role == "admin"
    val isReporter = currentUser?.id == incident?.reporterId

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(incident?.referenceCode ?: "Incident Dossier", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadIncidentDetail(incidentId) }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = CivicNavy,
                    titleContentColor = Color.White,
                    navigationIconContentColor = Color.White,
                    actionIconContentColor = Color.White
                )
            )
        }
    ) { innerPadding ->
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            color = Color(0xFFF8FAFC)
        ) {
            if (incident == null) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = CivicTeal)
                }
            } else {
                val inc = incident!!
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Header card
                    item {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            shape = RoundedCornerShape(16.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .background(
                                                if (inc.priority == "P1_CRITICAL") Color(0xFFFEE2E2) else Color(0xFFFEF3C7),
                                                shape = RoundedCornerShape(6.dp)
                                            )
                                            .padding(horizontal = 8.dp, vertical = 3.dp)
                                    ) {
                                        Text(
                                            text = inc.priority,
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = if (inc.priority == "P1_CRITICAL") Color(0xFFDC2626) else Color(0xFFD97706)
                                        )
                                    }

                                    Box(
                                        modifier = Modifier
                                            .background(
                                                when (inc.status) {
                                                    "resolved" -> Color(0xFFD1FAE5)
                                                    "on_scene" -> Color(0xFFDBEAFE)
                                                    "acknowledged" -> Color(0xFFFEF3C7)
                                                    else -> Color(0xFFFEE2E2)
                                                },
                                                shape = RoundedCornerShape(6.dp)
                                            )
                                            .padding(horizontal = 8.dp, vertical = 3.dp)
                                    ) {
                                        Text(
                                            text = inc.status.replace("_", " ").uppercase(),
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = when (inc.status) {
                                                "resolved" -> Color(0xFF059669)
                                                "on_scene" -> Color(0xFF2563EB)
                                                "acknowledged" -> Color(0xFFD97706)
                                                else -> Color(0xFFDC2626)
                                            }
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(10.dp))

                                Text(
                                    text = inc.title,
                                    fontSize = 18.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = CivicNavy
                                )

                                Spacer(modifier = Modifier.height(4.dp))

                                Text(
                                    text = inc.description,
                                    fontSize = 13.sp,
                                    color = Color(0xFF475569),
                                    lineHeight = 18.sp
                                )

                                Spacer(modifier = Modifier.height(12.dp))

                                Divider(color = Color(0xFFE2E8F0))

                                Spacer(modifier = Modifier.height(10.dp))

                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Column {
                                        Text("Location", fontSize = 10.sp, color = Color(0xFF94A3B8))
                                        Text(
                                            inc.locationAddress ?: "Designated Sector",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = CivicNavy
                                        )
                                    }

                                    Column {
                                        Text("Responder", fontSize = 10.sp, color = Color(0xFF94A3B8))
                                        Text(
                                            inc.assignedResponderName ?: "Awaiting Claim",
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.SemiBold,
                                            color = CivicTeal
                                        )
                                    }
                                }
                            }
                        }
                    }

                    // Operational Actions for Responders
                    if (inc.status != "resolved") {
                        item {
                            Card(
                                colors = CardDefaults.cardColors(containerColor = Color(0xFFF1F5F9)),
                                shape = RoundedCornerShape(16.dp),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Column(
                                    modifier = Modifier.padding(14.dp),
                                    verticalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    Text(
                                        text = "OPERATIONAL STATUS CONTROLS",
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFF64748B)
                                    )

                                    if (isResponderOrAdmin && inc.status == "reported") {
                                        Button(
                                            onClick = { viewModel.acknowledgeIncident(inc.id) },
                                            modifier = Modifier.fillMaxWidth().testTag("detail_claim_button"),
                                            colors = ButtonDefaults.buttonColors(containerColor = CivicTeal),
                                            shape = RoundedCornerShape(10.dp)
                                        ) {
                                            Text("Claim & Acknowledge Incident", fontWeight = FontWeight.Bold)
                                        }
                                    }

                                    if (isResponderOrAdmin && inc.status == "acknowledged") {
                                        Button(
                                            onClick = { viewModel.updateIncidentStatus(inc.id, "responder_en_route", "En route to scene.") },
                                            modifier = Modifier.fillMaxWidth(),
                                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2563EB)),
                                            shape = RoundedCornerShape(10.dp)
                                        ) {
                                            Text("Mark Responder En Route", fontWeight = FontWeight.Bold)
                                        }
                                    }

                                    if (isResponderOrAdmin && inc.status == "responder_en_route") {
                                        Button(
                                            onClick = { viewModel.updateIncidentStatus(inc.id, "on_scene", "Arrived on scene.") },
                                            modifier = Modifier.fillMaxWidth(),
                                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF7E22CE)),
                                            shape = RoundedCornerShape(10.dp)
                                        ) {
                                            Text("Log On-Scene Arrival", fontWeight = FontWeight.Bold)
                                        }
                                    }

                                    if (isResponderOrAdmin && inc.status == "on_scene") {
                                        Button(
                                            onClick = { viewModel.updateIncidentStatus(inc.id, "resolved", "Threat contained and verified safe.") },
                                            modifier = Modifier.fillMaxWidth(),
                                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF059669)),
                                            shape = RoundedCornerShape(10.dp)
                                        ) {
                                            Text("Resolve & Close Incident", fontWeight = FontWeight.Bold)
                                        }
                                    }

                                    // Resident resolution option
                                    if (isReporter && inc.status != "resolved") {
                                        OutlinedButton(
                                            onClick = { viewModel.updateIncidentStatus(inc.id, "false_alarm", "Resident marked as resolved / safe.") },
                                            modifier = Modifier.fillMaxWidth(),
                                            shape = RoundedCornerShape(10.dp)
                                        ) {
                                            Text("Mark Safe / Cancel Alarm")
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Chronological Timeline Header
                    item {
                        Text(
                            text = "Chronological Audit Trail",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = CivicNavy
                        )
                    }

                    // Timeline entries
                    items(inc.statusHistory) { item ->
                        TimelineRow(item)
                    }

                    item {
                        Spacer(modifier = Modifier.height(24.dp))
                    }
                }
            }
        }
    }
}

@Composable
fun TimelineRow(item: IncidentStatusHistoryItem) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.Top
        ) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .background(
                        when (item.status) {
                            "resolved" -> Color(0xFF059669)
                            "on_scene" -> Color(0xFF2563EB)
                            "acknowledged" -> Color(0xFFD97706)
                            else -> Color(0xFFDC2626)
                        },
                        shape = CircleShape
                    )
                    .padding(top = 4.dp)
            )

            Spacer(modifier = Modifier.width(10.dp))

            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = item.status.replace("_", " ").uppercase(),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = CivicNavy
                    )
                    Text(
                        text = item.updatedByName ?: "System",
                        fontSize = 10.sp,
                        color = Color(0xFF64748B)
                    )
                }

                if (!item.notes.isNullOrBlank()) {
                    Text(
                        text = item.notes,
                        fontSize = 12.sp,
                        color = Color(0xFF475569),
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }
            }
        }
    }
}
