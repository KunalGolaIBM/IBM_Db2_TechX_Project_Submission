package com.example.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import com.example.ui.screens.*
import com.example.ui.theme.CivicNavy
import com.example.ui.theme.CivicTeal
import com.example.ui.viewmodel.SafetyViewModel

sealed class Screen(val route: String, val title: String, val icon: ImageVector? = null) {
    object Onboarding : Screen("onboarding", "Onboarding")
    object Auth : Screen("auth?isRegister={isRegister}", "Authentication") {
        fun createRoute(isRegister: Boolean) = "auth?isRegister=$isRegister"
    }
    object ResidentHome : Screen("resident_home", "Home", Icons.Default.Home)
    object ReportIncident : Screen("report_incident", "Report")
    object IncidentDetail : Screen("incident_detail/{incidentId}", "Incident Detail") {
        fun createRoute(id: Int) = "incident_detail/$id"
    }
    object Contacts : Screen("contacts", "Contacts")
    object ChildSafety : Screen("child_safety", "Child Care")
    object ElderCare : Screen("elder_care", "Elder Care")
    object Community : Screen("community", "Hazards", Icons.Default.Warning)
    object Responder : Screen("responder", "Command", Icons.Default.Security)
    object Settings : Screen("settings", "Settings", Icons.Default.Settings)
}

@Composable
fun SafetyNavHost(
    viewModel: SafetyViewModel = viewModel()
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val currentUser by viewModel.currentUser.collectAsState()

    // Determine bottom bar visibility
    val showBottomBar = currentRoute in listOf(
        Screen.ResidentHome.route,
        Screen.Community.route,
        Screen.Responder.route,
        Screen.Settings.route
    )

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar(
                    containerColor = Color.White,
                    tonalElevation = 6.dp
                ) {
                    NavigationBarItem(
                        selected = currentRoute == Screen.ResidentHome.route,
                        onClick = {
                            navController.navigate(Screen.ResidentHome.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Home, contentDescription = "Home") },
                        label = { Text("Home") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = CivicNavy,
                            selectedTextColor = CivicNavy,
                            indicatorColor = Color(0xFFCCFBF1)
                        )
                    )

                    NavigationBarItem(
                        selected = currentRoute == Screen.Community.route,
                        onClick = {
                            navController.navigate(Screen.Community.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Warning, contentDescription = "Hazards") },
                        label = { Text("Hazards") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = CivicNavy,
                            selectedTextColor = CivicNavy,
                            indicatorColor = Color(0xFFCCFBF1)
                        )
                    )

                    if (currentUser?.role == "responder" || currentUser?.role == "admin") {
                        NavigationBarItem(
                            selected = currentRoute == Screen.Responder.route,
                            onClick = {
                                navController.navigate(Screen.Responder.route) {
                                    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(Icons.Default.Security, contentDescription = "Responder") },
                            label = { Text("Patrol") },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = CivicNavy,
                                selectedTextColor = CivicNavy,
                                indicatorColor = Color(0xFFCCFBF1)
                            )
                        )
                    }

                    NavigationBarItem(
                        selected = currentRoute == Screen.Settings.route,
                        onClick = {
                            navController.navigate(Screen.Settings.route) {
                                popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(Icons.Default.Settings, contentDescription = "Settings") },
                        label = { Text("Settings") },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = CivicNavy,
                            selectedTextColor = CivicNavy,
                            indicatorColor = Color(0xFFCCFBF1)
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Onboarding.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Onboarding.route) {
                OnboardingScreen(
                    onNavigateToAuth = { isRegister ->
                        navController.navigate(Screen.Auth.createRoute(isRegister))
                    }
                )
            }

            composable(
                route = Screen.Auth.route,
                arguments = listOf(navArgument("isRegister") {
                    type = NavType.BoolType
                    defaultValue = false
                })
            ) { backStackEntry ->
                val isRegister = backStackEntry.arguments?.getBoolean("isRegister") ?: false
                AuthScreen(
                    viewModel = viewModel,
                    initialRegister = isRegister,
                    onAuthSuccess = {
                        navController.navigate(Screen.ResidentHome.route) {
                            popUpTo(Screen.Onboarding.route) { inclusive = true }
                        }
                    }
                )
            }

            composable(Screen.ResidentHome.route) {
                ResidentHomeScreen(
                    viewModel = viewModel,
                    onNavigateToIncidentDetail = { id ->
                        navController.navigate(Screen.IncidentDetail.createRoute(id))
                    },
                    onNavigateToReport = {
                        navController.navigate(Screen.ReportIncident.route)
                    },
                    onNavigateToContacts = {
                        navController.navigate(Screen.Contacts.route)
                    },
                    onNavigateToChildSafety = {
                        navController.navigate(Screen.ChildSafety.route)
                    },
                    onNavigateToElderCare = {
                        navController.navigate(Screen.ElderCare.route)
                    }
                )
            }

            composable(
                route = Screen.IncidentDetail.route,
                arguments = listOf(navArgument("incidentId") { type = NavType.IntType })
            ) { backStackEntry ->
                val incId = backStackEntry.arguments?.getInt("incidentId") ?: 0
                IncidentDetailScreen(
                    incidentId = incId,
                    viewModel = viewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.ReportIncident.route) {
                ReportIncidentScreen(
                    viewModel = viewModel,
                    onIncidentCreated = { id ->
                        navController.navigate(Screen.IncidentDetail.createRoute(id)) {
                            popUpTo(Screen.ResidentHome.route)
                        }
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Contacts.route) {
                TrustedContactsScreen(
                    viewModel = viewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.ChildSafety.route) {
                ChildJourneyScreen(
                    viewModel = viewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.ElderCare.route) {
                ElderCareScreen(
                    viewModel = viewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Responder.route) {
                ResponderScreen(
                    viewModel = viewModel,
                    onNavigateToIncidentDetail = { id ->
                        navController.navigate(Screen.IncidentDetail.createRoute(id))
                    },
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Community.route) {
                CommunityAlertsScreen(
                    viewModel = viewModel,
                    onBack = { navController.popBackStack() }
                )
            }

            composable(Screen.Settings.route) {
                SettingsScreen(
                    viewModel = viewModel,
                    onLogout = {
                        navController.navigate(Screen.Onboarding.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                )
            }
        }
    }
}
