import { useLocation, useNavigate } from "react-router-dom";
import { LogOut01, Moon01, CloudSun01 } from "@untitledui/icons";
import { HeaderNavigationBase } from "@/components/application/app-navigation/header-navigation";
import { Button } from "@/components/base/buttons/button";
import { useDarkMode } from "../hooks/useDarkMode";

interface NavBarProps {
  onLogout: () => void;
}

const navItems = [
  { label: "Dashboard", href: "/" },
  { label: "Institutions", href: "/institutions" },
  { label: "Researchers", href: "/researchers" },
  { label: "Admin", href: "/admin" },
];

export default function NavBar({ onLogout }: NavBarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { dark, toggle } = useDarkMode();

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
          <Button
            color="tertiary"
            size="sm"
            iconLeading={dark ? CloudSun01 : Moon01}
            onClick={toggle}
          />
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
