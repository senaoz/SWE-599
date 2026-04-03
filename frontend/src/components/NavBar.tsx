import { useLocation, useNavigate } from "react-router-dom";
import { LogOut01 } from "@untitledui/icons";
import { HeaderNavigationBase } from "@/components/application/app-navigation/header-navigation";
import { Button } from "@/components/base/buttons/button";

interface NavBarProps {
  onLogout: () => void;
}

const navItems = [
  { label: "Dashboard", href: "/" },
  { label: "Institutions", href: "/institutions" },
  { label: "Admin", href: "/admin" },
];

export default function NavBar({ onLogout }: NavBarProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout();
    navigate("/login");
  };

  return (
    <HeaderNavigationBase
      activeUrl={location.pathname}
      items={navItems}
      actions={
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-primary">BOUN Paper Recommender</span>
          <Button
            color="secondary"
            size="sm"
            iconLeading={LogOut01}
            onClick={handleLogout}
          >
            Logout
          </Button>
        </div>
      }
    />
  );
}
