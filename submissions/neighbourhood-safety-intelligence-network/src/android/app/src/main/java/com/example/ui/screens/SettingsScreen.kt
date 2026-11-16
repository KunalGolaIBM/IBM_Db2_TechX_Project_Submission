package com.example.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
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
import com.example.ui.theme.CivicNavy
import com.example.ui.theme.CivicTeal
import com.example.ui.theme.EmergencyRed
import com.example.ui.viewmodel.SafetyViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SafetyViewModel,
    onLogout: () -> Unit
) {
    val currentUser by viewModel.currentUser.collectAsState()
    val apiBaseUrl by viewModel.apiBaseUrl.collectAsState()

    var inputUrl by remember { mutableStateOf(apiBaseUrl) }
    var urlSavedNotice by remember { mutableStateOf(false) }

    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Profile & Settings", fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = CivicNavy,
                    titleContentColor = Color.White
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
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Profile Card
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(48.dp)
                                    .background(CivicNavy, shape = RoundedCornerShape(14.dp)),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Person,
                                    contentDescription = null,
                                    tint = CivicTeal,
                                    modifier = Modifier.size(28.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = currentUser?.fullName ?: "Resident User",
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = CivicNavy
                                )
                                Text(
                                    text = currentUser?.email ?: "",
                                    fontSize = 12.sp,
                                    color = Color(0xFF64748B)
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(14.dp))
                        Divider(color = Color(0xFFE2E8F0))
                        Spacer(modifier = Modifier.height(10.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("Account Role", fontSize = 12.sp, color = Color(0xFF64748B))
                            Text(
                                text = (currentUser?.role ?: "resident").uppercase(),
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = CivicTeal
                            )
                        }

                        if (!currentUser?.address.isNullOrBlank()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text("Address", fontSize = 12.sp, color = Color(0xFF64748B))
                                Text(
                                    text = currentUser!!.address!!,
                                    fontSize = 12.sp,
                                    color = CivicNavy
                                )
                            }
                        }
                    }
                }

                // Backend API URL Configuration
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(
                            text = "BACKEND SERVER CONFIGURATION",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF64748B),
                            letterSpacing = 1.sp
                        )

                        Text(
                            text = "Configurable endpoint for Android Emulator or physical device testing.",
                            fontSize = 12.sp,
                            color = Color(0xFF475569)
                        )

                        OutlinedTextField(
                            value = inputUrl,
                            onValueChange = {
                                inputUrl = it
                                urlSavedNotice = false
                            },
                            label = { Text("API Base URL") },
                            modifier = Modifier.fillMaxWidth().testTag("api_url_input"),
                            singleLine = true
                        )

                        Text(
                            text = "Default emulator: http://10.0.2.2:8000\nPhysical device: Use developer machine's LAN IP",
                            fontSize = 11.sp,
                            color = Color(0xFF94A3B8),
                            lineHeight = 15.sp
                        )

                        Button(
                            onClick = {
                                viewModel.updateApiBaseUrl(inputUrl.trim())
                                urlSavedNotice = true
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = CivicNavy),
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.testTag("api_url_save_button")
                        ) {
                            Text("Save Backend URL")
                        }

                        if (urlSavedNotice) {
                            Text(
                                text = "✓ Backend URL updated successfully.",
                                fontSize = 11.sp,
                                color = Color(0xFF059669),
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }

                // Emergency Helplines Card
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = "NATIONAL EMERGENCY HELPLINES",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = EmergencyRed,
                            letterSpacing = 1.sp
                        )

                        HelplineItem("Unified Emergency Hotline", "112")
                        HelplineItem("Police Emergency", "100")
                        HelplineItem("Women in Distress Helpline", "1091")
                        HelplineItem("Childline Assistance", "1098")
                        HelplineItem("Senior Citizen Elderline", "14567")
                    }
                }

                // Sign Out Button
                Button(
                    onClick = {
                        viewModel.logout()
                        onLogout()
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                        .testTag("settings_logout_button"),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF1F5F9)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "Sign Out of Account",
                        color = Color(0xFFDC2626),
                        fontWeight = FontWeight.Bold
                    )
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

@Composable
fun HelplineItem(title: String, number: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(title, fontSize = 12.sp, color = Color(0xFF475569))
        Text(number, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = CivicNavy)
    }
}
