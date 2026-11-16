package com.example.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.example.ui.theme.CivicNavy
import com.example.ui.theme.CivicTeal
import com.example.ui.viewmodel.SafetyViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ElderCareScreen(
    viewModel: SafetyViewModel,
    onBack: () -> Unit
) {
    val checkIns by viewModel.elderCheckIns.collectAsState()
    val requests by viewModel.assistanceRequests.collectAsState()

    var showRequestDialog by remember { mutableStateOf(false) }
    var reqType by remember { mutableStateOf("medicine") }
    var description by remember { mutableStateOf("") }
    var urgency by remember { mutableStateOf("medium") }

    LaunchedEffect(Unit) {
        viewModel.fetchElderData()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Senior Citizen Welfare", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = CivicNavy,
                    titleContentColor = Color.White,
                    navigationIconContentColor = Color.White
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
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Welfare Checkin Card
                item {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = CivicNavy),
                        shape = RoundedCornerShape(20.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier.padding(18.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text(
                                text = "DAILY WELLNESS CHECK-IN",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = CivicTeal,
                                letterSpacing = 1.sp
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Text(
                                text = "Keep family guardians and local volunteer carers assured of your safety.",
                                fontSize = 12.sp,
                                color = Color(0xFFCBD5E1),
                                modifier = Modifier.padding(horizontal = 8.dp)
                            )
                            Spacer(modifier = Modifier.height(14.dp))

                            Button(
                                onClick = { viewModel.submitElderCheckIn("good") },
                                colors = ButtonDefaults.buttonColors(containerColor = CivicTeal),
                                shape = RoundedCornerShape(12.dp),
                                modifier = Modifier.fillMaxWidth().testTag("elder_checkin_button")
                            ) {
                                Icon(Icons.Default.CheckCircle, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("I Am Safe & Well Today", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }

                // Assistance Section Header
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Community Assistance Requests",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = CivicNavy
                        )

                        TextButton(onClick = { showRequestDialog = true }) {
                            Text("+ Request Help", color = CivicTeal, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }
                }

                if (requests.isEmpty()) {
                    item {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Box(modifier = Modifier.padding(20.dp), contentAlignment = Alignment.Center) {
                                Text(
                                    text = "No active requests. Request medicines or grocery runs above.",
                                    fontSize = 12.sp,
                                    color = Color(0xFF64748B)
                                )
                            }
                        }
                    }
                } else {
                    items(requests) { r ->
                        Card(
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            shape = RoundedCornerShape(14.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(modifier = Modifier.padding(14.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(
                                        text = "${r.requestType.replaceFirstChar { it.uppercase() }} Assistance",
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = CivicNavy
                                    )
                                    Box(
                                        modifier = Modifier
                                            .background(
                                                if (r.status == "completed") Color(0xFFD1FAE5) else Color(0xFFFEF3C7),
                                                shape = RoundedCornerShape(4.dp)
                                            )
                                            .padding(horizontal = 6.dp, vertical = 2.dp)
                                    ) {
                                        Text(
                                            text = r.status.uppercase(),
                                            fontSize = 9.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = if (r.status == "completed") Color(0xFF059669) else Color(0xFFD97706)
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = r.description,
                                    fontSize = 12.sp,
                                    color = Color(0xFF475569)
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    if (showRequestDialog) {
        AlertDialog(
            onDismissRequest = { showRequestDialog = false },
            title = { Text("Request Community Assistance", fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = reqType,
                        onValueChange = { reqType = it },
                        label = { Text("Type (medicine, grocery, mobility)") },
                        modifier = Modifier.fillMaxWidth().testTag("req_type_input"),
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = description,
                        onValueChange = { description = it },
                        label = { Text("Description (e.g. Prescription refill)") },
                        modifier = Modifier.fillMaxWidth().testTag("req_desc_input"),
                        minLines = 2
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (description.isNotBlank()) {
                            viewModel.createAssistanceRequest(reqType, description, urgency)
                            description = ""
                            showRequestDialog = false
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = CivicNavy),
                    modifier = Modifier.testTag("req_submit_button")
                ) {
                    Text("Submit Request")
                }
            },
            dismissButton = {
                OutlinedButton(onClick = { showRequestDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}
