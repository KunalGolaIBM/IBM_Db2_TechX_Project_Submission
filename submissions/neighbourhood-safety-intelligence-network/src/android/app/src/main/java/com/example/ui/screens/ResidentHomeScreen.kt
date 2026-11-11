package com.example.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.model.Incident
import com.example.ui.theme.CivicNavy
import com.example.ui.theme.CivicTeal
import com.example.ui.theme.EmergencyRed
import com.example.ui.viewmodel.SafetyViewModel

@Composable
fun ResidentHomeScreen(
    viewModel: SafetyViewModel,
    onNavigateToIncidentDetail: (Int) -> Unit,
    onNavigateToReport: () -> Unit,
    onNavigateToContacts: () -> Unit,
    onNavigateToChildSafety: () -> Unit,
    onNavigateToElderCare: () -> Unit
) {
    val currentUser by viewModel.currentUser.collectAsState()
    val incidents by viewModel.incidents.collectAsState()
    val insights by viewModel.communityInsights.collectAsState()
    val contacts by viewModel.contacts.collectAsState()
    val successMessage by viewModel.successMessage.collectAsState()

    var showSosConfirmDialog by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        viewModel.fetchAllData()
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = Color(0xFFF8FAFC)
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Welcome Header
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "Hello, ${currentUser?.fullName ?: "Resident"}",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold,
                            color = CivicNavy
                        )
                        Text(
                            text = currentUser?.address ?: "Oak Ridge Apartments, Sector 4",
                            fontSize = 12.sp,
                            color = Color(0xFF64748B)
                        )
                    }

                    IconButton(
                        onClick = { viewModel.fetchAllData() },
                        modifier = Modifier
                            .background(Color.White, shape = CircleShape)
                            .size(40.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh",
                            tint = CivicNavy
                        )
                    }
                }
            }

            // Success Notice
            if (successMessage != null) {
                item {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = Color(0xFFD1FAE5)),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.CheckCircle,
                                contentDescription = null,
                                tint = Color(0xFF059669),
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = successMessage!!,
                                fontSize = 12.sp,
                                color = Color(0xFF065F46)
                            )
                        }
                    }
                }
            }

            // Big SOS Trigger Hero Card
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = CivicNavy),
                    shape = RoundedCornerShape(24.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "DISTRESS EMERGENCY ASSISTANCE",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = CivicTeal,
                            letterSpacing = 1.sp
                        )

                        Spacer(modifier = Modifier.height(16.dp))

                        // Big Button
                        Button(
                            onClick = { showSosConfirmDialog = true },
                            modifier = Modifier
                                .size(110.dp)
                                .testTag("home_sos_button"),
                            shape = CircleShape,
                            colors = ButtonDefaults.buttonColors(containerColor = EmergencyRed),
                            elevation = ButtonDefaults.buttonElevation(defaultElevation = 8.dp)
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Icon(
                                    imageVector = Icons.Default.Warning,
                                    contentDescription = "SOS Warning",
                                    tint = Color.White,
                                    modifier = Modifier.size(32.dp)
                                )
                                Text(
                                    text = "SOS",
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = Color.White
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(14.dp))

                        Text(
                            text = "Alerts ${contacts.size} trusted contacts & active patrol units",
                            fontSize = 12.sp,
                            color = Color(0xFFCBD5E1)
                        )
                    }
                }
            }

            // Quick Actions 2x2 Grid
            item {
                Text(
                    text = "Civic Safety Modules",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = CivicNavy
                )
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    QuickActionCard(
                        title = "Report Hazard",
                        subtitle = "Dark road, loiter",
                        icon = Icons.Default.AddAlert,
                        iconBg = Color(0xFFFEF3C7),
                        iconTint = Color(0xFFD97706),
                        modifier = Modifier.weight(1f),
                        onClick = onNavigateToReport
                    )
                    QuickActionCard(
                        title = "Child Transit",
                        subtitle = "Arrival monitor",
                        icon = Icons.Default.Visibility,
                        iconBg = Color(0xFFDBEAFE),
                        iconTint = Color(0xFF2563EB),
                        modifier = Modifier.weight(1f),
                        onClick = onNavigateToChildSafety
                    )
                }
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    QuickActionCard(
                        title = "Elder Care",
                        subtitle = "Daily check-in",
                        icon = Icons.Default.Favorite,
                        iconBg = Color(0xFFCCFBF1),
                        iconTint = Color(0xFF0D9488),
                        modifier = Modifier.weight(1f),
                        onClick = onNavigateToElderCare
                    )
                    QuickActionCard(
                        title = "Contacts (${contacts.size})",
                        subtitle = "SOS guardians",
                        icon = Icons.Default.Group,
                        iconBg = Color(0xFFF3E8FF),
                        iconTint = Color(0xFF7E22CE),
                        modifier = Modifier.weight(1f),
                        onClick = onNavigateToContacts
                    )
                }
            }

            // AI Safety Advisory Banner
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .background(CivicNavy, shape = RoundedCornerShape(8.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.Shield,
                                contentDescription = null,
                                tint = CivicTeal,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "AI SAFETY ADVISORY",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = CivicTeal
                                )
                                Text(
                                    text = "Score: ${insights?.safetyHealthScore ?: 92}/100",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF059669)
                                )
                            }
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = insights?.aiSafetyAdvisory
                                    ?: "Sector 4 verified clear. Evening volunteer patrols active along major corridors.",
                                fontSize = 12.sp,
                                color = Color(0xFF334155),
                                lineHeight = 16.sp
                            )
                        }
                    }
                }
            }

            // Recent Incidents Header
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Active Incidents & Alerts",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = CivicNavy
                    )
                    Text(
                        text = "${incidents.size} Total",
                        fontSize = 12.sp,
                        color = Color(0xFF64748B)
                    )
                }
            }

            // Incidents Items
            if (incidents.isEmpty()) {
                item {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(24.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No open incidents. Your neighbourhood is safe.",
                                fontSize = 12.sp,
                                color = Color(0xFF64748B)
                            )
                        }
                    }
                }
            } else {
                items(incidents) { inc ->
                    IncidentCard(
                        incident = inc,
                        onClick = { onNavigateToIncidentDetail(inc.id) }
                    )
                }
            }

            item {
                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }

    // Two-Step Confirmation Dialog for SOS
    if (showSosConfirmDialog) {
        AlertDialog(
            onDismissRequest = { showSosConfirmDialog = false },
            title = {
                Text(
                    text = "🚨 Confirm Emergency SOS?",
                    fontWeight = FontWeight.Bold,
                    fontSize = 18.sp,
                    color = EmergencyRed
                )
            },
            text = {
                Text(
                    text = "This will immediately send your current GPS coordinates to ${contacts.size} trusted contacts and nearby on-duty volunteer responders. Responders must acknowledge within 120 seconds.",
                    fontSize = 13.sp,
                    color = Color(0xFF475569)
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSosConfirmDialog = false
                        viewModel.triggerSOS { created ->
                            onNavigateToIncidentDetail(created.id)
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = EmergencyRed),
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.testTag("sos_confirm_button")
                ) {
                    Text("Yes, Send Distress Alert", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                OutlinedButton(
                    onClick = { showSosConfirmDialog = false },
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun QuickActionCard(
    title: String,
    subtitle: String,
    icon: ImageVector,
    iconBg: Color,
    iconTint: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = modifier.clickable { onClick() }
    ) {
        Column(
            modifier = Modifier.padding(14.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .background(iconBg, shape = RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = iconTint,
                    modifier = Modifier.size(20.dp)
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = title,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = CivicNavy
            )
            Text(
                text = subtitle,
                fontSize = 10.sp,
                color = Color(0xFF64748B)
            )
        }
    }
}

@Composable
fun IncidentCard(
    incident: Incident,
    onClick: () -> Unit
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(14.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = incident.referenceCode,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF64748B)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Box(
                        modifier = Modifier
                            .background(
                                if (incident.priority == "P1_CRITICAL") Color(0xFFFEE2E2) else Color(0xFFFEF3C7),
                                shape = RoundedCornerShape(4.dp)
                            )
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = incident.priority,
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (incident.priority == "P1_CRITICAL") Color(0xFFDC2626) else Color(0xFFD97706)
                        )
                    }
                }

                Box(
                    modifier = Modifier
                        .background(
                            when (incident.status) {
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
                        text = incident.status.replace("_", " ").uppercase(),
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = when (incident.status) {
                            "resolved" -> Color(0xFF059669)
                            "on_scene" -> Color(0xFF2563EB)
                            "acknowledged" -> Color(0xFFD97706)
                            else -> Color(0xFFDC2626)
                        }
                    )
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = incident.title,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                color = CivicNavy
            )

            Text(
                text = incident.description,
                fontSize = 12.sp,
                color = Color(0xFF475569),
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.LocationOn,
                        contentDescription = null,
                        tint = Color(0xFF94A3B8),
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = incident.locationAddress ?: "Designated Sector",
                        fontSize = 11.sp,
                        color = Color(0xFF64748B)
                    )
                }

                Icon(
                    imageVector = Icons.Default.ChevronRight,
                    contentDescription = "View",
                    tint = CivicTeal,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}
