        AOS.init({
            duration: 800,
            once: true
        });

        // Toggle Sidebar Mobile
        document.getElementById("menuToggle").onclick = function () {
            document.getElementById("sidebarMenu").classList.toggle("active");
        };

        // Close button for mobile sidebar
        document.getElementById("closeSidebar").onclick = function () {
            document.getElementById("sidebarMenu").classList.remove("active");
        };