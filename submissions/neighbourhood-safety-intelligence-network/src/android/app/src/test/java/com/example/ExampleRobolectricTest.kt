package com.example

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.example.data.api.ApiClient
import com.example.data.model.Incident
import com.example.ui.viewmodel.SafetyViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ExampleRobolectricTest {

    @Test
    fun readStringFromContext_matchesNeighbourhoodSafety() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val appName = context.getString(R.string.app_name)
        assertEquals("Neighbourhood Safety", appName)
    }

    @Test
    fun apiBaseUrl_defaultConfiguredToEmulatorHost() {
        assertTrue(ApiClient.baseUrl.contains("10.0.2.2") || ApiClient.baseUrl.contains("8000"))
        ApiClient.baseUrl = "http://192.168.1.100:8000"
        assertEquals("http://192.168.1.100:8000/", ApiClient.baseUrl)
        // Reset to default
        ApiClient.baseUrl = "http://10.0.2.2:8000"
    }

    @Test
    fun safetyViewModel_initialStateEmptyAndNotLoading() {
        val viewModel = SafetyViewModel()
        assertEquals(null, viewModel.currentUser.value)
        assertEquals(false, viewModel.isLoading.value)
        assertTrue(viewModel.incidents.value.isEmpty())
        assertTrue(viewModel.contacts.value.isEmpty())
    }
}
